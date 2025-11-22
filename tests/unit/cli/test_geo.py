"""Tests for CLI geo commands."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.geo import geo
from paidsearchnav.core.models import (
    GeographicLevel,
    GeoPerformanceAnalysisResult,
    GeoPerformanceData,
    LocationInsight,
)


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_api_client():
    """Mock Google Ads API client."""
    return Mock()


@pytest.fixture
def mock_analyzer():
    """Mock GeoPerformanceAnalyzer."""
    analyzer = Mock()
    analyzer.analyze = AsyncMock()
    return analyzer


@pytest.fixture
def sample_performance_data():
    """Sample performance data for testing."""
    start_date = datetime.now() - timedelta(days=90)
    end_date = datetime.now()

    return [
        GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="123",
            campaign_name="Test Campaign",
            location_name="New York",
            location_id="1023191",
            geographic_level=GeographicLevel.CITY,
            impressions=10000,
            clicks=500,
            conversions=50.0,
            cost_micros=1000000000,  # $1000 in micros
            revenue_micros=5000000000,  # $5000 in micros
            start_date=start_date,
            end_date=end_date,
        ),
        GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="123",
            campaign_name="Test Campaign",
            location_name="Los Angeles",
            location_id="1023192",
            geographic_level=GeographicLevel.CITY,
            impressions=8000,
            clicks=400,
            conversions=30.0,
            cost_micros=800000000,  # $800 in micros
            revenue_micros=3000000000,  # $3000 in micros
            start_date=start_date,
            end_date=end_date,
        ),
    ]


@pytest.fixture
def sample_insights():
    """Sample insights for testing."""
    return [
        LocationInsight(
            location_name="New York",
            geographic_level=GeographicLevel.CITY,
            performance_score=85.0,
            cpa_vs_average=-0.15,  # 15% better than average
            roas_vs_average=0.25,  # 25% better than average
            conversion_rate_vs_average=0.1,
            impression_share=0.556,
            cost_share=0.55,
            conversion_share=0.625,
            recommended_action="Increase budget",
            budget_recommendation="Increase by 20%",
            targeting_recommendation="Expand to surrounding areas",
        ),
        LocationInsight(
            location_name="Los Angeles",
            geographic_level=GeographicLevel.CITY,
            performance_score=65.0,
            cpa_vs_average=0.12,  # 12% worse than average
            roas_vs_average=-0.06,  # 6% worse than average
            conversion_rate_vs_average=-0.05,
            impression_share=0.444,
            cost_share=0.45,
            conversion_share=0.375,
            recommended_action="Optimize targeting",
            budget_recommendation="Maintain current budget",
            targeting_recommendation="Refine keyword targeting",
        ),
    ]


@pytest.fixture
def sample_result(sample_performance_data, sample_insights):
    """Sample analysis result."""
    from paidsearchnav.core.models import GeoPerformanceSummary

    now = datetime.now()

    summary = GeoPerformanceSummary(
        customer_id="1234567890",
        analysis_date=now,
        date_range_start=now - timedelta(days=90),
        date_range_end=now,
        total_locations=2,
        total_cost=1800.0,
        total_conversions=80.0,
        average_cpa=22.5,
        average_roas=4.44,
        top_performing_locations=[sample_insights[0]],  # New York
        underperforming_locations=[sample_insights[1]],  # Los Angeles
        location_distribution={"CITY": 2},
    )

    from paidsearchnav.core.models import AnalysisMetrics

    metrics = AnalysisMetrics(
        total_campaigns=1,
        total_ad_groups=1,
        total_keywords=0,
        total_cost=1800.0,
        total_clicks=900,
        total_impressions=18000,
        total_conversions=80.0,
        average_ctr=0.05,
        average_cpc=2.0,
        average_conversion_rate=0.089,
    )

    return GeoPerformanceAnalysisResult(
        customer_id="1234567890",
        analyzer_name="GeoPerformanceAnalyzer",
        start_date=now - timedelta(days=90),
        end_date=now,
        metrics=metrics,
        performance_data=sample_performance_data,
        insights=sample_insights,
        summary=summary,
    )


class TestGeoAnalyzeCommand:
    """Test the geo analyze command."""

    def test_analyze_with_default_options(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test analyze command with default options."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Run command
                result = cli_runner.invoke(
                    geo, ["analyze", "--customer-id", "1234567890"]
                )

                # Verify API client created
                mock_create_client.assert_called_once()

                # Verify analyzer created with default min values
                mock_analyzer_class.assert_called_once_with(
                    api_client=mock_api_client,
                    min_impressions=100,
                    min_clicks=10,
                )

                # Verify analyze called with correct parameters
                mock_analyzer.analyze.assert_called_once()
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["customer_id"] == "1234567890"
                assert call_args["geographic_level"] == "CITY"
                assert isinstance(call_args["start_date"], datetime)
                assert isinstance(call_args["end_date"], datetime)

                # Verify output
                assert result.exit_code == 0
                assert "Analyzing CITY level performance" in result.output
                assert "Analysis completed for 1 geographic levels" in result.output

    def test_analyze_with_custom_date_range(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test analyze command with custom date range."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Run command with custom dates
                result = cli_runner.invoke(
                    geo,
                    [
                        "analyze",
                        "--customer-id",
                        "1234567890",
                        "--start-date",
                        "2024-01-01",
                        "--end-date",
                        "2024-01-31",
                    ],
                )

                # Verify analyze called with custom dates
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["start_date"] == datetime(2024, 1, 1)
                assert call_args["end_date"] == datetime(2024, 1, 31)

                assert result.exit_code == 0

    def test_analyze_with_multiple_location_types(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test analyze command with multiple location types."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Run command with multiple location types
                result = cli_runner.invoke(
                    geo,
                    [
                        "analyze",
                        "--customer-id",
                        "1234567890",
                        "--location-types",
                        "CITY,STATE,POSTAL_CODE",
                    ],
                )

                # Verify analyze called 3 times for each location type
                assert mock_analyzer.analyze.call_count == 3
                geographic_levels = [
                    call[1]["geographic_level"]
                    for call in mock_analyzer.analyze.call_args_list
                ]
                assert "CITY" in geographic_levels
                assert "STATE" in geographic_levels
                assert "POSTAL_CODE" in geographic_levels

                assert result.exit_code == 0
                assert "Analysis completed for 3 geographic levels" in result.output

    def test_analyze_with_campaign_filter(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test analyze command with campaign ID filter."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Run command with campaign IDs
                result = cli_runner.invoke(
                    geo,
                    [
                        "analyze",
                        "--customer-id",
                        "1234567890",
                        "--campaign-ids",
                        "123,456,789",
                    ],
                )

                # Verify analyze called with campaign IDs
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["campaign_ids"] == ["123", "456", "789"]

                assert result.exit_code == 0

    def test_analyze_json_output(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test analyze command with JSON output."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "geo_analysis.json"

                # Run command with JSON output
                result = cli_runner.invoke(
                    geo,
                    [
                        "analyze",
                        "--customer-id",
                        "1234567890",
                        "--format",
                        "json",
                        "--output-file",
                        str(output_file),
                    ],
                )

                assert result.exit_code == 0
                assert output_file.exists()

                # Verify JSON content
                with open(output_file) as f:
                    data = json.load(f)
                    assert len(data) == 2
                    assert data[0]["location_name"] == "New York"
                    assert data[0]["performance_score"] == 85.0
                    assert data[1]["location_name"] == "Los Angeles"

    def test_analyze_csv_output(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test analyze command with CSV output."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "geo_analysis.csv"

                # Run command with CSV output
                result = cli_runner.invoke(
                    geo,
                    [
                        "analyze",
                        "--customer-id",
                        "1234567890",
                        "--format",
                        "csv",
                        "--output-file",
                        str(output_file),
                    ],
                )

                assert result.exit_code == 0
                assert output_file.exists()

                # Verify CSV content
                import pandas as pd

                df = pd.read_csv(output_file)
                assert len(df) == 2
                assert df.iloc[0]["location_name"] == "New York"
                assert df.iloc[0]["performance_score"] == 85.0

    def test_analyze_handles_error(self, cli_runner, mock_api_client, mock_analyzer):
        """Test analyze command error handling."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks to raise error
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.side_effect = Exception("API error")

                # Run command
                result = cli_runner.invoke(
                    geo, ["analyze", "--customer-id", "1234567890"]
                )

                assert result.exit_code == 1
                assert "Error during analysis: API error" in result.output


class TestGeoCompareCommand:
    """Test the geo compare command."""

    def test_compare_with_default_options(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test compare command with default options."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York,Los Angeles",
                    ],
                )

                # Verify analyzer created
                mock_analyzer_class.assert_called_once_with(api_client=mock_api_client)

                # Verify analyze called
                mock_analyzer.analyze.assert_called_once()
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["customer_id"] == "1234567890"
                assert call_args["geographic_level"] == "CITY"

                # Verify output
                assert result.exit_code == 0
                assert "Comparing 2 locations" in result.output
                assert "Comparison completed for 2 locations" in result.output

    def test_compare_with_custom_date_range(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test compare command with custom date range."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Run command with custom date range
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York,Los Angeles",
                        "--date-range",
                        "custom",
                        "--start-date",
                        "2024-01-01",
                        "--end-date",
                        "2024-01-31",
                    ],
                )

                # Verify dates
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["start_date"] == datetime(2024, 1, 1)
                assert call_args["end_date"] == datetime(2024, 1, 31)

                assert result.exit_code == 0

    def test_compare_with_predefined_date_ranges(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result
    ):
        """Test compare command with predefined date ranges."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Test last_week
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York",
                        "--date-range",
                        "last_week",
                    ],
                )
                assert result.exit_code == 0

                # Test last_month
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York",
                        "--date-range",
                        "last_month",
                    ],
                )
                assert result.exit_code == 0

    def test_compare_missing_dates_for_custom_range(self, cli_runner):
        """Test compare command fails when custom range missing dates."""
        result = cli_runner.invoke(
            geo,
            [
                "compare",
                "--customer-id",
                "1234567890",
                "--locations",
                "New York",
                "--date-range",
                "custom",
            ],
        )

        assert result.exit_code == 1
        assert "Custom date range requires --start-date and --end-date" in result.output

    def test_compare_no_data_for_locations(
        self, cli_runner, mock_api_client, mock_analyzer
    ):
        """Test compare command when no data found for locations."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks with empty result
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                from paidsearchnav.core.models import (
                    AnalysisMetrics,
                    GeoPerformanceSummary,
                )

                empty_summary = GeoPerformanceSummary(
                    customer_id="1234567890",
                    analysis_date=datetime.now(),
                    date_range_start=datetime.now() - timedelta(days=90),
                    date_range_end=datetime.now(),
                    total_locations=0,
                    total_cost=0.0,
                    total_conversions=0.0,
                    average_cpa=0.0,
                    average_roas=0.0,
                    top_performing_locations=[],
                    underperforming_locations=[],
                    location_distribution={},
                )

                empty_metrics = AnalysisMetrics(
                    total_campaigns=0,
                    total_ad_groups=0,
                    total_keywords=0,
                    total_cost=0.0,
                    total_clicks=0,
                    total_impressions=0,
                    total_conversions=0.0,
                    average_ctr=0.0,
                    average_cpc=0.0,
                    average_conversion_rate=0.0,
                )

                empty_result = GeoPerformanceAnalysisResult(
                    customer_id="1234567890",
                    analyzer_name="GeoPerformanceAnalyzer",
                    start_date=datetime.now() - timedelta(days=90),
                    end_date=datetime.now(),
                    metrics=empty_metrics,
                    performance_data=[],
                    insights=[],
                    summary=empty_summary,
                )
                mock_analyzer.analyze.return_value = empty_result

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "Unknown City",
                    ],
                )

                assert result.exit_code == 0
                assert "No data found for specified locations" in result.output

    def test_compare_json_output(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test compare command with JSON output."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "comparison.json"

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York,Los Angeles",
                        "--format",
                        "json",
                        "--output-file",
                        str(output_file),
                    ],
                )

                assert result.exit_code == 0
                assert output_file.exists()

                # Verify JSON content
                with open(output_file) as f:
                    data = json.load(f)
                    assert len(data) == 2
                    assert data[0]["location_name"] == "New York"
                    assert data[0]["cpa"] == 20.0

    def test_compare_handles_error(self, cli_runner, mock_api_client, mock_analyzer):
        """Test compare command error handling."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks to raise error
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.side_effect = Exception("API error")

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York",
                    ],
                )

                assert result.exit_code == 1
                assert "Error during comparison: API error" in result.output


class TestGeoExportRecommendationsCommand:
    """Test the geo export-recommendations command."""

    def test_export_recommendations_with_customer_id(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test export-recommendations command with customer ID."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "recommendations.csv"

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "export-recommendations",
                        "--customer-id",
                        "1234567890",
                        "--output-file",
                        str(output_file),
                    ],
                )

                # Verify analyzer called
                mock_analyzer.analyze.assert_called_once()
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["customer_id"] == "1234567890"
                assert call_args["geographic_level"] == "CITY"

                assert result.exit_code == 0
                assert output_file.exists()
                assert "Recommendations exported to" in result.output

    def test_export_recommendations_requires_id(self, cli_runner):
        """Test export-recommendations requires either audit-id or customer-id."""
        result = cli_runner.invoke(geo, ["export-recommendations"])

        assert result.exit_code == 1
        assert "Either --audit-id or --customer-id must be provided" in result.output

    def test_export_recommendations_with_audit_id(
        self, cli_runner, mock_api_client, mock_analyzer
    ):
        """Test export-recommendations with audit ID (not implemented)."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer

                # Run command
                result = cli_runner.invoke(
                    geo, ["export-recommendations", "--audit-id", "AUDIT123"]
                )

                # Should show not implemented message
                assert result.exit_code == 0
                assert "Using audit_id to derive customer_id" in result.output

    def test_export_recommendations_with_filters(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test export-recommendations with priority and location type filters."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "recommendations.csv"

                # Run command with filters
                result = cli_runner.invoke(
                    geo,
                    [
                        "export-recommendations",
                        "--customer-id",
                        "1234567890",
                        "--priority",
                        "high",
                        "--location-type",
                        "STATE",
                        "--output-file",
                        str(output_file),
                    ],
                )

                # Verify location type used
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["geographic_level"] == "STATE"

                assert result.exit_code == 0
                assert output_file.exists()

    def test_export_recommendations_grouping_options(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test export-recommendations with different grouping options."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Test different grouping options
                for group_by in [
                    "location",
                    "store_location",
                    "campaign",
                    "performance_tier",
                ]:
                    output_file = tmp_path / f"recommendations_{group_by}.csv"

                    result = cli_runner.invoke(
                        geo,
                        [
                            "export-recommendations",
                            "--customer-id",
                            "1234567890",
                            "--group-by",
                            group_by,
                            "--output-file",
                            str(output_file),
                        ],
                    )

                    assert result.exit_code == 0
                    assert output_file.exists()

    def test_export_recommendations_json_format(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test export-recommendations with JSON format."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "recommendations.json"

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "export-recommendations",
                        "--customer-id",
                        "1234567890",
                        "--format",
                        "json",
                        "--output-file",
                        str(output_file),
                    ],
                )

                assert result.exit_code == 0
                assert output_file.exists()

                # Verify JSON content
                with open(output_file) as f:
                    data = json.load(f)
                    assert isinstance(data, list)
                    assert len(data) == 2  # Two insights

    def test_export_recommendations_excel_format_fallback(
        self, cli_runner, mock_api_client, mock_analyzer, sample_result, tmp_path
    ):
        """Test export-recommendations Excel format fallback to CSV."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.return_value = sample_result

                # Output file
                output_file = tmp_path / "recommendations.xlsx"

                # Run command
                result = cli_runner.invoke(
                    geo,
                    [
                        "export-recommendations",
                        "--customer-id",
                        "1234567890",
                        "--format",
                        "excel",
                        "--output-file",
                        str(output_file),
                    ],
                )

                assert result.exit_code == 0
                # Should create CSV file instead if openpyxl not available
                csv_file = tmp_path / "recommendations.csv"
                assert csv_file.exists() or output_file.exists()

    def test_export_recommendations_handles_error(
        self, cli_runner, mock_api_client, mock_analyzer
    ):
        """Test export-recommendations error handling."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mocks to raise error
                mock_create_client.return_value = mock_api_client
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze.side_effect = Exception("API error")

                # Run command
                result = cli_runner.invoke(
                    geo, ["export-recommendations", "--customer-id", "1234567890"]
                )

                assert result.exit_code == 1
                assert "Error during export: API error" in result.output


class TestGeoCommandIntegration:
    """Integration tests for geo commands."""

    def test_geo_group_exists(self, cli_runner):
        """Test that geo command group exists."""
        result = cli_runner.invoke(geo, ["--help"])
        assert result.exit_code == 0
        assert "Geographic performance analysis commands" in result.output
        assert "analyze" in result.output
        assert "compare" in result.output
        assert "export-recommendations" in result.output

    def test_analyze_command_help(self, cli_runner):
        """Test analyze command help."""
        result = cli_runner.invoke(geo, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--customer-id" in result.output
        assert "--locations" in result.output
        assert "--location-types" in result.output
        assert "--start-date" in result.output
        assert "--format" in result.output

    def test_compare_command_help(self, cli_runner):
        """Test compare command help."""
        result = cli_runner.invoke(geo, ["compare", "--help"])
        assert result.exit_code == 0
        assert "--customer-id" in result.output
        assert "--locations" in result.output
        assert "--date-range" in result.output
        assert "--metrics" in result.output

    def test_export_recommendations_help(self, cli_runner):
        """Test export-recommendations command help."""
        result = cli_runner.invoke(geo, ["export-recommendations", "--help"])
        assert result.exit_code == 0
        assert "--audit-id" in result.output
        assert "--customer-id" in result.output
        assert "--group-by" in result.output
        assert "--priority" in result.output
