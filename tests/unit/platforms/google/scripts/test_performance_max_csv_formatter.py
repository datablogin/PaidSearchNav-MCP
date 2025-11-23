"""Tests for Performance Max CSV formatter."""

import json

import pytest

from paidsearchnav_mcp.platforms.google.scripts.performance_max_csv_formatter import (
    PerformanceMaxCSVFormatter,
)


class TestPerformanceMaxCSVFormatter:
    """Test cases for PerformanceMaxCSVFormatter."""

    @pytest.fixture
    def formatter(self):
        """Create a PerformanceMaxCSVFormatter instance."""
        return PerformanceMaxCSVFormatter()

    @pytest.fixture
    def sample_monitoring_data(self):
        """Sample Performance Max monitoring data."""
        return [
            {
                "campaignId": "12345",
                "campaignName": "Test Performance Max Campaign",
                "campaignType": "PERFORMANCE_MAX",
                "status": "ENABLED",
                "biddingStrategy": "TARGET_ROAS",
                "targetRoas": 3.5,
                "targetCpa": 0.0,
                "dailyBudget": 100.00,
                "cost": 250.75,
                "impressions": 15000,
                "clicks": 450,
                "conversions": 12.5,
                "conversionValue": 875.25,
                "allConversions": 13.2,
                "viewThroughConversions": 2.1,
                "ctr": 3.0,
                "cpc": 0.56,
                "cpa": 20.06,
                "roas": 3.49,
                "conversionRate": 2.78,
                "performanceFlags": ["LOW_CTR", "GOOD_ROAS"],
                "date": "2024-03-15",
            },
            {
                "campaignId": "67890",
                "campaignName": "Another PMax Campaign",
                "campaignType": "PERFORMANCE_MAX",
                "status": "ENABLED",
                "biddingStrategy": "TARGET_CPA",
                "targetRoas": 0.0,
                "targetCpa": 25.00,
                "dailyBudget": 75.00,
                "cost": 180.50,
                "impressions": 8500,
                "clicks": 320,
                "conversions": 8.0,
                "conversionValue": 600.00,
                "allConversions": 8.5,
                "viewThroughConversions": 1.5,
                "ctr": 3.76,
                "cpc": 0.56,
                "cpa": 22.56,
                "roas": 3.32,
                "conversionRate": 2.50,
                "performanceFlags": [],
                "date": "2024-03-15",
            },
        ]

    @pytest.fixture
    def sample_asset_data(self):
        """Sample asset optimization data."""
        return [
            {
                "assetId": "asset_001",
                "assetName": "Lifestyle Image 1",
                "assetType": "IMAGE",
                "fieldType": "MARKETING_IMAGE",
                "assetGroupId": "ag_001",
                "assetGroupName": "Lifestyle Assets",
                "campaignId": "12345",
                "campaignName": "Test Performance Max Campaign",
                "impressions": 5000,
                "clicks": 150,
                "conversions": 4.5,
                "ctr": 3.0,
                "conversionRate": 3.0,
                "performanceCategory": "HIGH",
                "adStrength": "GOOD",
                "needsImprovement": False,
                "improvementReason": "",
                "date": "2024-03-15",
            },
            {
                "assetId": "asset_002",
                "assetName": "Product Image 1",
                "assetType": "IMAGE",
                "fieldType": "MARKETING_IMAGE",
                "assetGroupId": "ag_002",
                "assetGroupName": "Product Assets",
                "campaignId": "12345",
                "campaignName": "Test Performance Max Campaign",
                "impressions": 2000,
                "clicks": 30,
                "conversions": 0.5,
                "ctr": 1.5,
                "conversionRate": 1.67,
                "performanceCategory": "LOW",
                "adStrength": "POOR",
                "needsImprovement": True,
                "improvementReason": "Low ad strength: POOR",
                "date": "2024-03-15",
            },
        ]

    @pytest.fixture
    def sample_geographic_data(self):
        """Sample geographic performance data."""
        return [
            {
                "locationId": "1026201",
                "locationType": "CITY",
                "targetLocationMatch": {
                    "name": "Dallas",
                    "state": "Texas",
                    "isPriority": True,
                },
                "campaignIds": ["12345", "67890"],
                "totalImpressions": 12000,
                "totalClicks": 360,
                "totalCost": 200.50,
                "totalConversions": 10.0,
                "totalConversionValue": 750.00,
                "allConversions": 10.5,
                "viewThroughConversions": 1.2,
                "ctr": 3.0,
                "cpc": 0.56,
                "cpa": 20.05,
                "roas": 3.74,
                "conversionRate": 2.78,
                "performanceCategory": "GOOD",
                "dateRange": "2024-03-01 to 2024-03-15",
            }
        ]

    def test_format_monitoring_csv(self, formatter, sample_monitoring_data):
        """Test Performance Max monitoring CSV formatting."""
        csv_output = formatter.format_performance_max_monitoring_csv(
            sample_monitoring_data
        )

        lines = csv_output.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows

        # Check header
        header = lines[0]
        assert "Campaign ID" in header
        assert "Campaign Name" in header
        assert "Campaign Type" in header
        assert "Bidding Strategy" in header
        assert "Target ROAS" in header
        assert "Performance Flags" in header

        # Check first data row
        first_row = lines[1].split(",")
        assert first_row[0] == "12345"  # Campaign ID
        assert "Test Performance Max Campaign" in lines[1]  # Campaign Name
        assert "PERFORMANCE_MAX" in lines[1]  # Campaign Type
        assert "TARGET_ROAS" in lines[1]  # Bidding Strategy

        # Check performance flags formatting
        assert "LOW_CTR;GOOD_ROAS" in lines[1]

    def test_format_asset_optimization_csv(self, formatter, sample_asset_data):
        """Test asset optimization CSV formatting."""
        csv_output = formatter.format_asset_optimization_csv(sample_asset_data)

        lines = csv_output.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows

        # Check header
        header = lines[0]
        assert "Asset ID" in header
        assert "Asset Name" in header
        assert "Asset Type" in header
        assert "Performance Category" in header
        assert "Ad Strength" in header

        # Check data content
        assert "asset_001" in lines[1]
        assert "Lifestyle Image 1" in lines[1]
        assert "HIGH" in lines[1]  # Performance category
        assert "GOOD" in lines[1]  # Ad strength

    def test_format_geographic_csv(self, formatter, sample_geographic_data):
        """Test geographic performance CSV formatting."""
        csv_output = formatter.format_geographic_performance_csv(sample_geographic_data)

        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Check header
        header = lines[0]
        assert "Location ID" in header
        assert "Location Name" in header
        assert "State" in header
        assert "Is Priority Location" in header
        assert "Performance Category" in header

        # Check data content
        assert "1026201" in lines[1]  # Location ID
        assert "Dallas" in lines[1]  # Location Name
        assert "Texas" in lines[1]  # State
        assert "True" in lines[1]  # Is Priority Location

    def test_format_empty_data(self, formatter):
        """Test CSV formatting with empty data."""
        csv_output = formatter.format_performance_max_monitoring_csv([])

        lines = csv_output.strip().split("\n")
        assert len(lines) == 1  # Only header

        header = lines[0]
        assert "Campaign ID" in header
        assert "Campaign Name" in header

    def test_format_bidding_optimization_csv(self, formatter):
        """Test bidding optimization CSV formatting."""
        sample_data = [
            {
                "strategyId": "bid_001",
                "strategyName": "Target ROAS 3.5",
                "strategyType": "TARGET_ROAS",
                "campaignId": "12345",
                "campaignName": "Test Campaign",
                "targetRoas": 3.5,
                "actualRoas": 3.2,
                "targetCpa": 0.0,
                "actualCpa": 22.50,
                "totalCost": 500.00,
                "totalConversions": 22.2,
                "totalConversionValue": 1600.00,
                "ctr": 2.8,
                "conversionRate": 2.5,
                "roasPerformanceRatio": 0.91,
                "cpaPerformanceRatio": 0.0,
                "roasTargetMet": False,
                "cpaTargetMet": False,
                "effectiveness": "FAIR",
                "impressionShare": 85.5,
                "budgetLostIS": 8.2,
                "rankLostIS": 6.3,
                "dateRange": "2024-03-01 to 2024-03-15",
            }
        ]

        csv_output = formatter.format_bidding_optimization_csv(sample_data)

        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Check header
        header = lines[0]
        assert "Strategy ID" in header
        assert "Target ROAS" in header
        assert "Actual ROAS" in header
        assert "Effectiveness Rating" in header

        # Check data
        assert "bid_001" in lines[1]
        assert "3.50" in lines[1]  # Target ROAS
        assert "3.20" in lines[1]  # Actual ROAS
        assert "FAIR" in lines[1]  # Effectiveness

    def test_format_cross_campaign_csv(self, formatter):
        """Test cross-campaign analysis CSV formatting."""
        sample_data = [
            {
                "searchTerm": "fitness gym near me",
                "pmaxCampaignId": "12345",
                "pmaxCampaignName": "Performance Max Campaign",
                "searchCampaignId": "67890",
                "searchCampaignName": "Search Campaign",
                "pmaxCost": 50.25,
                "searchCost": 35.75,
                "totalCost": 86.00,
                "pmaxConversions": 2.5,
                "searchConversions": 1.8,
                "pmaxCpa": 20.10,
                "searchCpa": 19.86,
                "pmaxRoas": 3.2,
                "searchRoas": 3.4,
                "betterPerformer": "SEARCH",
                "overlapSeverity": "MEDIUM",
                "recommendation": "Consider adding negative keyword to Performance Max",
                "dateRange": "2024-03-01 to 2024-03-15",
            }
        ]

        csv_output = formatter.format_cross_campaign_analysis_csv(sample_data)

        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Check header
        header = lines[0]
        assert "Search Term" in header
        assert "Better Performer" in header
        assert "Overlap Severity" in header

        # Check data
        assert "fitness gym near me" in lines[1]
        assert "SEARCH" in lines[1]
        assert "MEDIUM" in lines[1]

    def test_format_search_term_insights_csv(self, formatter):
        """Test search term insights CSV formatting."""
        sample_data = [
            {
                "searchTerm": "gym membership dallas",
                "campaignId": "12345",
                "campaignName": "Performance Max Campaign",
                "adGroupId": "ag_001",
                "adGroupName": "Default",
                "status": "SERVED",
                "impressions": 1500,
                "clicks": 45,
                "cost": 25.50,
                "conversions": 1.2,
                "conversionValue": 60.00,
                "ctr": 3.0,
                "cpc": 0.57,
                "cpa": 21.25,
                "roas": 2.35,
                "localIntent": True,
                "brandIntent": False,
                "commercialIntent": True,
                "specificLocation": "dallas",
                "intentType": "LOCATION_SPECIFIC",
                "negativeCandidate": False,
                "negativeReason": "",
                "searchPortCandidate": True,
                "portReason": "High performance local term",
                "date": "2024-03-15",
            }
        ]

        csv_output = formatter.format_search_term_insights_csv(sample_data)

        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Check header
        header = lines[0]
        assert "Search Term" in header
        assert "Local Intent" in header
        assert "Intent Type" in header
        assert "Search Port Candidate" in header

        # Check data
        assert "gym membership dallas" in lines[1]
        assert "True" in lines[1]  # Local Intent
        assert "LOCATION_SPECIFIC" in lines[1]

    def test_create_summary_report(self, formatter):
        """Test summary report creation."""
        results = {
            "campaigns_analyzed": 5,
            "asset_groups_analyzed": 15,
            "search_terms_analyzed": 450,
            "geographic_locations_analyzed": 8,
            "overlapping_terms_found": 25,
            "recommendations_generated": 12,
            "conflicts_identified": 3,
            "key_findings": [
                "High overlap between Performance Max and Search campaigns",
                "8 zombie assets identified",
            ],
            "top_recommendations": [
                "Add 15 negative keywords to reduce overlap",
                "Remove zombie assets to improve efficiency",
            ],
            "average_pmax_roas": 3.2,
            "average_search_roas": 2.8,
            "total_spend": 5500.75,
            "total_conversions": 125.5,
            "potential_savings": 450.25,
            "data_completeness": 0.95,
            "processing_errors": [],
            "warnings": ["Some asset-level data unavailable"],
        }

        summary_json = formatter.create_summary_report(results)
        summary = json.loads(summary_json)

        assert "execution_date" in summary
        assert summary["analysis_type"] == "performance_max_comprehensive"
        assert summary["summary"]["campaigns_analyzed"] == 5
        assert summary["summary"]["recommendations_generated"] == 12
        assert len(summary["key_findings"]) == 2
        assert summary["performance_metrics"]["average_pmax_roas"] == 3.2
        assert summary["data_quality"]["data_completeness"] == 0.95

    def test_format_for_s3_storage(self, formatter, sample_monitoring_data):
        """Test formatting data for S3 storage."""
        result = formatter.format_for_s3_storage(
            data_type="monitoring",
            data=sample_monitoring_data,
            customer_id="1234567890",
            date_range="LAST_30_DAYS",
        )

        assert "filename" in result
        assert "content" in result
        assert "content_type" in result

        # Check filename format
        filename = result["filename"]
        assert filename.startswith("pmax_monitoring_")
        assert "1234567890" in filename
        assert "LAST_30_DAYS" in filename
        assert filename.endswith(".csv")

        # Check content type
        assert result["content_type"] == "text/csv"

        # Check content is valid CSV
        csv_content = result["content"]
        lines = csv_content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows

    def test_format_for_s3_storage_invalid_type(self, formatter):
        """Test S3 formatting with invalid data type."""
        with pytest.raises(ValueError, match="Unknown data type"):
            formatter.format_for_s3_storage(
                data_type="invalid_type",
                data=[],
                customer_id="1234567890",
                date_range="LAST_30_DAYS",
            )

    def test_csv_formatting_with_special_characters(self, formatter):
        """Test CSV formatting with special characters in data."""
        sample_data = [
            {
                "campaignId": "12345",
                "campaignName": 'Test, Campaign "with" special chars',
                "campaignType": "PERFORMANCE_MAX",
                "status": "ENABLED",
                "biddingStrategy": "TARGET_ROAS",
                "targetRoas": 3.5,
                "targetCpa": 0.0,
                "dailyBudget": 100.00,
                "cost": 250.75,
                "impressions": 15000,
                "clicks": 450,
                "conversions": 12.5,
                "conversionValue": 875.25,
                "allConversions": 13.2,
                "viewThroughConversions": 2.1,
                "ctr": 3.0,
                "cpc": 0.56,
                "cpa": 20.06,
                "roas": 3.49,
                "conversionRate": 2.78,
                "performanceFlags": ["Flag with, comma", 'Flag with "quotes"'],
                "date": "2024-03-15",
            }
        ]

        csv_output = formatter.format_performance_max_monitoring_csv(sample_data)
        lines = csv_output.strip().split("\n")

        # Should handle special characters properly
        assert len(lines) == 2  # Header + 1 data row
        # CSV should be properly quoted/escaped
        assert (
            '"Test, Campaign ""with"" special chars"' in lines[1]
            or 'Test, Campaign "with" special chars' in lines[1]
        )

    def test_numeric_formatting_precision(self, formatter):
        """Test numeric value formatting precision."""
        sample_data = [
            {
                "campaignId": "12345",
                "campaignName": "Precision Test",
                "campaignType": "PERFORMANCE_MAX",
                "status": "ENABLED",
                "biddingStrategy": "TARGET_ROAS",
                "targetRoas": 3.123456789,  # Should be rounded to 2 decimal places
                "targetCpa": 0.0,
                "dailyBudget": 100.999,  # Should be rounded to 2 decimal places
                "cost": 250.123456,  # Should be rounded to 2 decimal places
                "impressions": 15000,
                "clicks": 450,
                "conversions": 12.567891,  # Should be rounded to 2 decimal places
                "conversionValue": 875.25,
                "allConversions": 13.2,
                "viewThroughConversions": 2.1,
                "ctr": 3.0,
                "cpc": 0.56,
                "cpa": 20.06,
                "roas": 3.49,
                "conversionRate": 2.78,
                "performanceFlags": [],
                "date": "2024-03-15",
            }
        ]

        csv_output = formatter.format_performance_max_monitoring_csv(sample_data)
        lines = csv_output.strip().split("\n")

        # Check numeric precision
        assert "3.12" in lines[1]  # targetRoas should be rounded
        assert "101.00" in lines[1]  # dailyBudget should be rounded
        assert "250.12" in lines[1]  # cost should be rounded
        assert "12.57" in lines[1]  # conversions should be rounded
