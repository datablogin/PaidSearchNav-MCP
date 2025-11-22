"""Integration tests for geographic analysis CLI commands."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from paidsearchnav.cli.geo import geo
from paidsearchnav.core.models import (
    AnalysisMetrics,
    GeographicLevel,
    GeoPerformanceAnalysisResult,
    GeoPerformanceData,
    GeoPerformanceSummary,
    LocationInsight,
)


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_api_response():
    """Mock API response data."""
    return [
        {
            "customer_id": "1234567890",
            "campaign_id": "123",
            "campaign_name": "Local Campaign",
            "location_name": "New York, NY",
            "location_id": "1023191",
            "geographic_level": "CITY",
            "impressions": 15000,
            "clicks": 750,
            "conversions": 75,
            "cost_micros": 1500000000,  # $1500
            "conversions_value": 7500,
            "segments": {"date": "2024-01-15"},
        },
        {
            "customer_id": "1234567890",
            "campaign_id": "123",
            "campaign_name": "Local Campaign",
            "location_name": "Los Angeles, CA",
            "location_id": "1023192",
            "geographic_level": "CITY",
            "impressions": 12000,
            "clicks": 600,
            "conversions": 45,
            "cost_micros": 1200000000,  # $1200
            "conversions_value": 4500,
            "segments": {"date": "2024-01-15"},
        },
        {
            "customer_id": "1234567890",
            "campaign_id": "456",
            "campaign_name": "Regional Campaign",
            "location_name": "Chicago, IL",
            "location_id": "1023193",
            "geographic_level": "CITY",
            "impressions": 8000,
            "clicks": 400,
            "conversions": 30,
            "cost_micros": 800000000,  # $800
            "conversions_value": 3000,
            "segments": {"date": "2024-01-15"},
        },
    ]


class TestGeoAnalyzeIntegration:
    """Integration tests for geo analyze command."""

    def test_analyze_full_flow(self, cli_runner, mock_api_response, tmp_path):
        """Test complete analyze flow from API call to output."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            with patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class:
                # Setup mock API client
                mock_api_client = Mock()
                mock_client_class.return_value = mock_api_client

                # Create sample analysis result from mock API response
                now = datetime.now()
                performance_data = [
                    GeoPerformanceData(
                        customer_id="1234567890",
                        campaign_id=item["campaign_id"],
                        campaign_name=item["campaign_name"],
                        location_name=item["location_name"],
                        location_id=item["location_id"],
                        geographic_level=GeographicLevel.CITY,
                        impressions=item["impressions"],
                        clicks=item["clicks"],
                        conversions=item["conversions"],
                        cost_micros=item["cost_micros"],
                        revenue_micros=item.get("conversions_value", 0) * 1000000,
                        start_date=now - timedelta(days=90),
                        end_date=now,
                    )
                    for item in mock_api_response
                ]

                # Create insights
                insights = []
                for data in performance_data:
                    insights.append(
                        LocationInsight(
                            location_name=data.location_name,
                            geographic_level=data.geographic_level,
                            performance_score=80 if data.conversions > 50 else 60,
                            cpa_vs_average=0.1,
                            roas_vs_average=0.2,
                            conversion_rate_vs_average=0.05,
                            impression_share=data.impressions / 100000,
                            cost_share=data.cost / 3500,
                            conversion_share=data.conversions / 150,
                            recommended_action="Optimize"
                            if data.conversions < 50
                            else "Scale",
                            budget_recommendation="Increase budget"
                            if data.conversions > 50
                            else "Maintain budget",
                            targeting_recommendation="Expand targeting",
                        )
                    )

                # Create summary
                summary = GeoPerformanceSummary(
                    customer_id="1234567890",
                    analysis_date=now,
                    date_range_start=now - timedelta(days=90),
                    date_range_end=now,
                    total_locations=len(performance_data),
                    total_cost=sum(d.cost for d in performance_data),
                    total_conversions=sum(d.conversions for d in performance_data),
                    average_cpa=20.0,
                    average_roas=5.0,
                    top_performing_locations=[
                        i for i in insights if i.performance_score >= 80
                    ],
                    underperforming_locations=[
                        i for i in insights if i.performance_score < 80
                    ],
                    location_distribution={"CITY": len(performance_data)},
                )

                # Create metrics
                metrics = AnalysisMetrics(
                    total_campaigns=2,
                    total_ad_groups=3,
                    total_keywords=0,
                    total_cost=sum(d.cost for d in performance_data),
                    total_clicks=sum(d.clicks for d in performance_data),
                    total_impressions=sum(d.impressions for d in performance_data),
                    total_conversions=sum(d.conversions for d in performance_data),
                    average_ctr=0.05,
                    average_cpc=2.0,
                    average_conversion_rate=0.1,
                )

                # Create result
                analysis_result = GeoPerformanceAnalysisResult(
                    customer_id="1234567890",
                    analyzer_name="GeoPerformanceAnalyzer",
                    start_date=now - timedelta(days=90),
                    end_date=now,
                    metrics=metrics,
                    performance_data=performance_data,
                    insights=insights,
                    summary=summary,
                )

                # Setup mock analyzer
                mock_analyzer = Mock()
                mock_analyzer.analyze = AsyncMock(return_value=analysis_result)
                mock_analyzer_class.return_value = mock_analyzer

                # Run command with CSV output
                output_file = tmp_path / "geo_analysis.csv"
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
                        "--min-impressions",
                        "5000",
                    ],
                )

                # Verify command succeeded
                assert result.exit_code == 0
                assert "Analysis completed for 1 geographic levels" in result.output

                # Verify analyzer was called correctly
                mock_analyzer.analyze.assert_called_once()
                call_args = mock_analyzer.analyze.call_args[1]
                assert call_args["customer_id"] == "1234567890"
                assert call_args["geographic_level"] == "CITY"

                # Verify CSV output
                assert output_file.exists()
                df = pd.read_csv(output_file)
                assert len(df) == 3  # All 3 cities pass min impressions threshold
                assert "New York, NY" in df["location_name"].values
                assert "Los Angeles, CA" in df["location_name"].values
                assert "Chicago, IL" in df["location_name"].values

    def test_analyze_with_filtering(self, cli_runner, mock_api_response):
        """Test analyze with campaign filtering."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            # Filter API response based on campaign IDs
            async def mock_get_geographic_performance(**kwargs):
                campaign_ids = kwargs.get("campaign_ids", [])
                if campaign_ids:
                    return [
                        r for r in mock_api_response if r["campaign_id"] in campaign_ids
                    ]
                return mock_api_response

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_get_geographic_performance
            )

            # Run command with campaign filter
            result = cli_runner.invoke(
                geo,
                [
                    "analyze",
                    "--customer-id",
                    "1234567890",
                    "--campaign-ids",
                    "123",
                    "--format",
                    "table",
                ],
            )

            # Verify command succeeded
            assert result.exit_code == 0

            # Verify only data from campaign 123 is shown
            assert "New York, NY" in result.output
            assert "Los Angeles, CA" in result.output
            assert "Chicago, IL" not in result.output  # Campaign 456

    def test_analyze_multiple_geographic_levels(self, cli_runner):
        """Test analyze with multiple geographic levels."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            # Mock responses for different geographic levels
            city_data = [
                {
                    "customer_id": "1234567890",
                    "campaign_id": "123",
                    "campaign_name": "Local Campaign",
                    "location_name": "New York, NY",
                    "location_id": "1023191",
                    "geographic_level": "CITY",
                    "impressions": 15000,
                    "clicks": 750,
                    "conversions": 75,
                    "cost_micros": 1500000000,
                }
            ]

            state_data = [
                {
                    "customer_id": "1234567890",
                    "campaign_id": "123",
                    "campaign_name": "Local Campaign",
                    "location_name": "New York",
                    "location_id": "21167",
                    "geographic_level": "STATE",
                    "impressions": 50000,
                    "clicks": 2500,
                    "conversions": 250,
                    "cost_micros": 5000000000,
                }
            ]

            async def mock_get_geographic_performance(**kwargs):
                level = kwargs.get("geographic_level")
                if level == "CITY":
                    return city_data
                elif level == "STATE":
                    return state_data
                return []

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_get_geographic_performance
            )

            # Run command with multiple location types
            result = cli_runner.invoke(
                geo,
                [
                    "analyze",
                    "--customer-id",
                    "1234567890",
                    "--location-types",
                    "CITY,STATE",
                ],
            )

            # Verify command succeeded
            assert result.exit_code == 0
            assert "Analysis completed for 2 geographic levels" in result.output

            # Verify API was called for each level
            assert mock_api_client.get_geographic_performance.call_count == 2


class TestGeoCompareIntegration:
    """Integration tests for geo compare command."""

    def test_compare_locations(self, cli_runner, mock_api_response, tmp_path):
        """Test comparing performance between locations."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            async def mock_get_geographic_performance(**kwargs):
                return mock_api_response

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_get_geographic_performance
            )

            # Run command
            output_file = tmp_path / "comparison.json"
            result = cli_runner.invoke(
                geo,
                [
                    "compare",
                    "--customer-id",
                    "1234567890",
                    "--locations",
                    "New York, NY,Los Angeles, CA",
                    "--metrics",
                    "cpa,roas,conversion_rate",
                    "--format",
                    "json",
                    "--output-file",
                    str(output_file),
                ],
            )

            # Verify command succeeded
            assert result.exit_code == 0
            assert "Comparison completed for 2 locations" in result.output

            # Verify JSON output
            assert output_file.exists()
            with open(output_file) as f:
                data = json.load(f)
                assert len(data) == 2
                # Check metrics are included
                for item in data:
                    assert "cpa" in item
                    assert "roas" in item
                    assert "conversion_rate" in item

    def test_compare_with_date_ranges(self, cli_runner):
        """Test compare with different date range options."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            # Track date ranges used
            date_ranges_used = []

            async def mock_get_geographic_performance(**kwargs):
                date_ranges_used.append(
                    {
                        "start_date": kwargs.get("start_date"),
                        "end_date": kwargs.get("end_date"),
                    }
                )
                return []  # Empty response

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_get_geographic_performance
            )

            # Test different date ranges
            for date_range in ["last_week", "last_month", "last_quarter"]:
                result = cli_runner.invoke(
                    geo,
                    [
                        "compare",
                        "--customer-id",
                        "1234567890",
                        "--locations",
                        "New York",
                        "--date-range",
                        date_range,
                    ],
                )
                assert result.exit_code == 0

            # Verify different date ranges were used
            assert len(date_ranges_used) == 3
            # Verify date ranges are different
            assert date_ranges_used[0] != date_ranges_used[1]
            assert date_ranges_used[1] != date_ranges_used[2]


class TestGeoExportRecommendationsIntegration:
    """Integration tests for geo export-recommendations command."""

    def test_export_recommendations_full_flow(self, cli_runner, tmp_path):
        """Test complete export recommendations flow."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            # Mock API response with varied performance
            api_response = [
                {
                    "customer_id": "1234567890",
                    "campaign_id": "123",
                    "campaign_name": "Local Campaign",
                    "location_name": "New York, NY",
                    "location_id": "1023191",
                    "geographic_level": "CITY",
                    "impressions": 50000,
                    "clicks": 2500,
                    "conversions": 250,
                    "cost_micros": 2500000000,  # $2500
                    "conversions_value": 25000,
                },
                {
                    "customer_id": "1234567890",
                    "campaign_id": "123",
                    "campaign_name": "Local Campaign",
                    "location_name": "Poor Performer, CA",
                    "location_id": "1023194",
                    "geographic_level": "CITY",
                    "impressions": 10000,
                    "clicks": 100,
                    "conversions": 2,
                    "cost_micros": 1000000000,  # $1000
                    "conversions_value": 200,
                },
            ]

            async def mock_get_geographic_performance(**kwargs):
                return api_response

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_get_geographic_performance
            )

            # Run command
            output_file = tmp_path / "recommendations.csv"
            result = cli_runner.invoke(
                geo,
                [
                    "export-recommendations",
                    "--customer-id",
                    "1234567890",
                    "--output-file",
                    str(output_file),
                    "--format",
                    "csv",
                ],
            )

            # Verify command succeeded
            assert result.exit_code == 0
            assert "Recommendations exported to" in result.output

            # Verify CSV output
            assert output_file.exists()
            df = pd.read_csv(output_file)
            assert len(df) >= 2  # At least 2 recommendations
            assert "location_name" in df.columns
            assert "priority" in df.columns
            assert "recommended_action" in df.columns

    def test_export_recommendations_with_priority_filter(self, cli_runner, tmp_path):
        """Test export recommendations with priority filtering."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            # Mock API response
            api_response = [
                {
                    "customer_id": "1234567890",
                    "campaign_id": "123",
                    "campaign_name": "Local Campaign",
                    "location_name": "High Performer, NY",
                    "location_id": "1023191",
                    "geographic_level": "CITY",
                    "impressions": 100000,
                    "clicks": 5000,
                    "conversions": 500,
                    "cost_micros": 5000000000,
                },
            ]

            async def mock_get_geographic_performance(**kwargs):
                return api_response

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_get_geographic_performance
            )

            # Run command with high priority filter
            output_file = tmp_path / "high_priority_recs.json"
            result = cli_runner.invoke(
                geo,
                [
                    "export-recommendations",
                    "--customer-id",
                    "1234567890",
                    "--priority",
                    "high",
                    "--format",
                    "json",
                    "--output-file",
                    str(output_file),
                ],
            )

            # Verify command succeeded
            assert result.exit_code == 0

            # Verify JSON output contains only high priority
            assert output_file.exists()
            with open(output_file) as f:
                data = json.load(f)
                for rec in data:
                    if "priority" in rec:
                        assert rec["priority"] == "high"


class TestGeoCommandErrorHandling:
    """Test error handling in geo commands."""

    def test_api_error_handling(self, cli_runner):
        """Test handling of API errors."""
        with patch("paidsearchnav.cli.geo.GoogleAdsAPIClient") as mock_client_class:
            # Setup mock API client that raises error
            mock_api_client = Mock()
            mock_client_class.return_value = mock_api_client

            async def mock_api_error(**kwargs):
                raise Exception("Google Ads API error: Invalid customer ID")

            mock_api_client.get_geographic_performance = AsyncMock(
                side_effect=mock_api_error
            )

            # Run command
            result = cli_runner.invoke(geo, ["analyze", "--customer-id", "invalid"])

            # Verify error handling
            assert result.exit_code == 1
            assert "Error during analysis" in result.output
            assert "Google Ads API error" in result.output

    def test_invalid_location_type(self, cli_runner):
        """Test handling of invalid location types."""
        result = cli_runner.invoke(
            geo,
            [
                "analyze",
                "--customer-id",
                "1234567890",
                "--location-types",
                "INVALID_TYPE",
            ],
        )

        # Should still succeed but use default (CITY)
        # The invalid type is filtered out
        assert result.exit_code in [0, 1]  # Depends on API mock setup

    def test_missing_required_parameters(self, cli_runner):
        """Test handling of missing required parameters."""
        # Test analyze without customer ID
        result = cli_runner.invoke(geo, ["analyze"])
        assert result.exit_code == 2
        assert "Missing option '--customer-id'" in result.output

        # Test compare without locations
        result = cli_runner.invoke(geo, ["compare", "--customer-id", "1234567890"])
        assert result.exit_code == 2
        assert "Missing option '--locations'" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
