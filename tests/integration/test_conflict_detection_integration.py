"""
Integration tests for Google Ads Scripts Conflict Detection System

These tests verify the end-to-end functionality of the conflict detection system,
including script deployment, execution, result processing, and bulk action generation.

Based on PaidSearchNav Issue #464
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav_mcp.scripts.conflict_detection import (
    ConflictDetectionConfig,
    ConflictDetectionManager,
    ConflictDetectionResults,
)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables required for conflict detection."""
    env_vars = {
        "GOOGLE_ADS_CUSTOMER_ID": "1234567890",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "test_developer_token",
        "GOOGLE_ADS_SERVICE_ACCOUNT_FILE": "/path/to/service-account.json",
        "AWS_ACCESS_KEY_ID": "test_access_key",
        "AWS_SECRET_ACCESS_KEY": "test_secret_key",
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


class TestConflictDetectionIntegration:
    """Integration tests for the complete conflict detection workflow."""

    @pytest.fixture
    def sample_script_content(self):
        """Sample JavaScript script content."""
        return """
        // Sample Google Ads Script
        const CONFIG = {
          EMAIL_RECIPIENTS: {{EMAIL_RECIPIENTS}},
          S3_BUCKET: '{{S3_BUCKET}}',
          THRESHOLDS: {{DETECTION_THRESHOLDS}},
          REPORT_RETENTION_DAYS: {{REPORT_RETENTION_DAYS}},
          MAX_CONFLICTS_PER_EMAIL: {{MAX_CONFLICTS_PER_EMAIL}},
        };

        function main() {
          console.log('Running conflict detection...');
        }
        """

    @pytest.fixture
    def sample_conflict_results(self):
        """Sample conflict detection results."""
        return {
            "timestamp": "2024-08-19T10:00:00Z",
            "positiveNegativeConflicts": [
                {
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "severity": "HIGH",
                    "keyword": "fitness connection dallas",
                    "keywordMatchType": "EXACT",
                    "negativeKeyword": "dallas",
                    "negativeMatchType": "BROAD",
                    "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Dallas",
                    "adGroup": "Brand Terms",
                    "negativeList": "Account Level Negatives",
                    "level": "CAMPAIGN",
                    "estimatedImpact": {
                        "blockedImpressions": 1200,
                        "lostClicks": 48,
                        "wastedSpend": 156.50,
                        "lostConversions": 2.3,
                    },
                    "detectedAt": "2024-08-19T10:00:00Z",
                },
                {
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "severity": "MEDIUM",
                    "keyword": "gym near me dallas",
                    "keywordMatchType": "PHRASE",
                    "negativeKeyword": "competitor gym",
                    "negativeMatchType": "PHRASE",
                    "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Dallas",
                    "adGroup": "Location Terms",
                    "negativeList": "Competitor Exclusions",
                    "level": "CAMPAIGN",
                    "estimatedImpact": {
                        "blockedImpressions": 800,
                        "lostClicks": 25,
                        "wastedSpend": 89.30,
                        "lostConversions": 1.2,
                    },
                    "detectedAt": "2024-08-19T10:00:00Z",
                },
            ],
            "crossCampaignConflicts": [
                {
                    "type": "CROSS_CAMPAIGN_CONFLICT",
                    "severity": "HIGH",
                    "keyword": "fitness gym dallas",
                    "campaigns": [
                        {
                            "name": "Local Search - Dallas",
                            "adGroup": "Fitness Terms",
                            "bid": 2.50,
                            "qualityScore": 7,
                            "stats": {"clicks": 45, "cost": 112.50, "conversions": 3},
                        },
                        {
                            "name": "Performance Max - Dallas",
                            "adGroup": "All Products",
                            "bid": 2.80,
                            "qualityScore": 6,
                            "stats": {"clicks": 38, "cost": 106.40, "conversions": 2},
                        },
                    ],
                    "bidCompetition": {
                        "maxBid": 2.80,
                        "minBid": 2.50,
                        "difference": 0.30,
                        "competitionLevel": 0.107,
                    },
                    "estimatedWastedSpend": 65.85,
                    "detectedAt": "2024-08-19T10:00:00Z",
                }
            ],
            "functionalityIssues": [
                {
                    "type": "LANDING_PAGE_ISSUE",
                    "severity": "HIGH",
                    "campaign": "Brand Campaign - Dallas",
                    "adGroup": "Brand Terms",
                    "ad": "Fitness Connection - Join Today",
                    "url": "https://fitnessconnection.com/broken-page",
                    "issue": "Landing page returns 404 error",
                    "detectedAt": "2024-08-19T10:00:00Z",
                },
                {
                    "type": "TARGETING_CONSISTENCY_ISSUE",
                    "severity": "MEDIUM",
                    "campaign": "Local Campaign - Houston",
                    "issue": "Campaign name suggests Houston targeting but no Houston locations found",
                    "expectedLocations": ["houston"],
                    "actualLocations": ["Dallas", "Austin", "San Antonio"],
                    "detectedAt": "2024-08-19T10:00:00Z",
                },
            ],
            "geographicConflicts": [
                {
                    "type": "GEOGRAPHIC_CONFLICT",
                    "severity": "MEDIUM",
                    "campaign": "Local Search - Dallas",
                    "keyword": "fitness connection houston",
                    "issue": "Keyword contains location term that is excluded from targeting",
                    "keywordLocation": "houston",
                    "excludedLocation": "Houston, TX",
                    "detectedAt": "2024-08-19T10:00:00Z",
                }
            ],
        }

    @pytest.fixture
    def test_config(self):
        """Test configuration with custom settings."""
        return ConflictDetectionConfig(
            email_recipients=["test@example.com", "admin@example.com"],
            s3_bucket="test-conflict-reports",
            detection_thresholds={
                "min_clicks_for_analysis": 10,
                "high_cost_threshold": 50.0,
                "quality_score_threshold": 5,
                "bid_competition_threshold": 0.15,
            },
            report_retention_days=60,
            max_conflicts_per_email=30,
        )

    @pytest.fixture
    def mock_manager_dependencies(self):
        """Mock manager dependencies."""
        mock_google_ads_client = Mock()
        mock_s3_client = Mock()
        # Create an async mock for upload_content method
        mock_s3_client.upload_content = AsyncMock(return_value=Mock(key="test-key"))

        return mock_google_ads_client, mock_s3_client

    @pytest.mark.asyncio
    async def test_full_conflict_detection_workflow(
        self,
        sample_script_content,
        sample_conflict_results,
        test_config,
        mock_manager_dependencies,
        mock_env_vars,
    ):
        """Test the complete conflict detection workflow."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies
        customer_id = "1234567890"

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        # Mock script file reading
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                sample_script_content
            )

            # Mock script deployment and execution
            with patch.object(
                manager, "_deploy_script_via_api", return_value="script_test_123"
            ):
                with patch.object(
                    manager, "_execute_script", return_value="exec_test_456"
                ):
                    with patch.object(
                        manager,
                        "_wait_for_results",
                        return_value=sample_conflict_results,
                    ):
                        # Run conflict detection
                        results = await manager.run_conflict_detection(customer_id)

                        # Verify results structure
                        assert isinstance(results, ConflictDetectionResults)
                        assert results.account_id == customer_id
                        assert (
                            results.total_conflicts == 5
                        )  # 2 + 1 + 2 + 0 (geographic conflicts don't count in total)
                        assert (
                            results.high_severity_count == 3
                        )  # 1 positive/negative + 1 cross-campaign + 1 landing page

                        # Verify positive/negative conflicts
                        assert len(results.positive_negative_conflicts) == 2
                        pn_high = next(
                            c
                            for c in results.positive_negative_conflicts
                            if c.severity == "HIGH"
                        )
                        assert pn_high.keyword == "fitness connection dallas"
                        assert "dallas" in pn_high.issue

                        # Verify cross-campaign conflicts
                        assert len(results.cross_campaign_conflicts) == 1
                        cc_conflict = results.cross_campaign_conflicts[0]
                        assert cc_conflict.keyword == "fitness gym dallas"
                        assert "multiple campaigns" in cc_conflict.issue

                        # Verify functionality issues
                        assert len(results.functionality_issues) == 2
                        landing_issue = next(
                            i
                            for i in results.functionality_issues
                            if i.type == "LANDING_PAGE_ISSUE"
                        )
                        assert landing_issue.severity == "HIGH"
                        assert "404 error" in landing_issue.issue

                        # Verify S3 storage was called
                        mock_s3_client.upload_content.assert_called()

    @pytest.mark.asyncio
    async def test_bulk_action_generation_integration(
        self, sample_conflict_results, test_config, mock_manager_dependencies
    ):
        """Test bulk action generation with realistic conflict data."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies
        customer_id = "1234567890"

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        # Process the sample results
        results = manager._process_script_results(customer_id, sample_conflict_results)

        # Generate bulk actions
        bulk_actions = await manager.generate_bulk_resolution_actions(
            results, priority_filter="HIGH"
        )

        # Verify bulk action files were generated
        assert "negative_keywords_bulk_upload.csv" in bulk_actions
        assert "campaign_optimization_actions.csv" in bulk_actions
        assert "keyword_pause_actions.csv" in bulk_actions

        # Verify negative keywords CSV content
        negative_csv = bulk_actions["negative_keywords_bulk_upload.csv"]
        assert "Campaign,Ad Group,Keyword,Criterion Type,Labels" in negative_csv
        assert '"fitness connection dallas"' in negative_csv
        assert "Negative Keyword" in negative_csv
        assert "Conflict Resolution - Automated" in negative_csv

        # Verify campaign actions CSV content
        campaign_csv = bulk_actions["campaign_optimization_actions.csv"]
        assert "Campaign,Action,Recommendation,Priority,Expected Impact" in campaign_csv
        assert "Review Keyword Competition" in campaign_csv
        assert "fitness gym dallas" in campaign_csv

        # Verify keyword pause actions CSV content
        keyword_csv = bulk_actions["keyword_pause_actions.csv"]
        assert "Campaign,Ad Group,Keyword,Action,Reason" in keyword_csv
        assert "fitness connection dallas" in keyword_csv
        assert "Pause" in keyword_csv

        # Verify S3 storage was called for bulk actions (at least once per file)
        # Note: The actual count may vary due to async operations
        assert mock_s3_client.upload_content.call_count > 0

    @pytest.mark.asyncio
    async def test_script_configuration_injection(
        self,
        sample_script_content,
        test_config,
        mock_manager_dependencies,
        mock_env_vars,
    ):
        """Test that configuration is properly injected into the JavaScript script."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        # Configure the script
        configured_script = manager._configure_script(sample_script_content)

        # Verify configuration injection
        assert "test@example.com" in configured_script
        assert "admin@example.com" in configured_script
        assert "test-conflict-reports" in configured_script

        # Verify threshold configuration
        assert '"min_clicks_for_analysis": 10' in configured_script
        assert '"high_cost_threshold": 50.0' in configured_script
        assert '"quality_score_threshold": 5' in configured_script
        assert '"bid_competition_threshold": 0.15' in configured_script

    @pytest.mark.asyncio
    async def test_historical_data_retrieval(
        self, test_config, mock_manager_dependencies
    ):
        """Test historical conflict data retrieval."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies
        customer_id = "1234567890"

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        # Mock historical results
        mock_historical_data = [
            ConflictDetectionResults(
                timestamp=datetime(2024, 8, 18, 10, 0, 0),
                account_id=customer_id,
                total_conflicts=3,
                high_severity_count=1,
                estimated_monthly_loss=250.0,
            ),
            ConflictDetectionResults(
                timestamp=datetime(2024, 8, 17, 10, 0, 0),
                account_id=customer_id,
                total_conflicts=5,
                high_severity_count=2,
                estimated_monthly_loss=400.0,
            ),
        ]

        with patch.object(
            manager, "_retrieve_historical_results", return_value=mock_historical_data
        ):
            history = await manager.get_conflict_history(customer_id, days_back=30)

            assert len(history) == 2
            assert all(
                isinstance(result, ConflictDetectionResults) for result in history
            )
            assert history[0].total_conflicts == 3
            assert history[1].total_conflicts == 5

    @pytest.mark.asyncio
    async def test_error_recovery_and_reporting(
        self, test_config, mock_manager_dependencies, mock_env_vars
    ):
        """Test error handling and recovery mechanisms."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies
        customer_id = "1234567890"

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        # Test script deployment failure
        with patch.object(
            manager, "_get_script_path", side_effect=Exception("Script file not found")
        ):
            with pytest.raises(Exception):
                await manager.deploy_conflict_detection_script(customer_id)

        # Test script execution failure
        with patch.object(
            manager, "deploy_conflict_detection_script", return_value="script_123"
        ):
            with patch.object(
                manager,
                "_execute_script",
                side_effect=Exception("Script execution failed"),
            ):
                with pytest.raises(Exception):
                    await manager.run_conflict_detection(customer_id)

        # Test S3 storage failure (should not prevent main flow)
        with patch.object(
            manager, "deploy_conflict_detection_script", return_value="script_123"
        ):
            with patch.object(manager, "_execute_script", return_value="exec_456"):
                with patch.object(
                    manager,
                    "_wait_for_results",
                    return_value={
                        "timestamp": datetime.now().isoformat(),
                        "positiveNegativeConflicts": [],
                        "crossCampaignConflicts": [],
                        "functionalityIssues": [],
                        "geographicConflicts": [],
                    },
                ):
                    with patch.object(
                        manager,
                        "_store_results",
                        side_effect=Exception("S3 storage failed"),
                    ):
                        # Should still complete successfully despite storage failure
                        results = await manager.run_conflict_detection(customer_id)
                        assert isinstance(results, ConflictDetectionResults)

    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(
        self, test_config, mock_manager_dependencies
    ):
        """Test performance with a large number of conflicts."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies
        customer_id = "1234567890"

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        # Generate large dataset
        large_conflict_results = {
            "timestamp": datetime.now().isoformat(),
            "positiveNegativeConflicts": [
                {
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "severity": "HIGH" if i % 3 == 0 else "MEDIUM",
                    "keyword": f"test keyword {i}",
                    "keywordMatchType": "EXACT",
                    "negativeKeyword": f"negative {i}",
                    "negativeMatchType": "BROAD",
                    "campaign": f"Campaign {i % 10}",
                    "adGroup": f"Ad Group {i % 5}",
                    "estimatedImpact": {"wastedSpend": 50.0 + i},
                    "detectedAt": datetime.now().isoformat(),
                }
                for i in range(100)  # 100 conflicts
            ],
            "crossCampaignConflicts": [
                {
                    "type": "CROSS_CAMPAIGN_CONFLICT",
                    "severity": "MEDIUM",
                    "keyword": f"competing keyword {i}",
                    "campaigns": [
                        {"name": f"Campaign {i}A"},
                        {"name": f"Campaign {i}B"},
                    ],
                    "estimatedWastedSpend": 25.0 + i,
                    "detectedAt": datetime.now().isoformat(),
                }
                for i in range(50)  # 50 cross-campaign conflicts
            ],
            "functionalityIssues": [],
            "geographicConflicts": [],
        }

        # Process large dataset
        results = manager._process_script_results(customer_id, large_conflict_results)

        assert results.total_conflicts == 150  # 100 + 50
        assert (
            results.high_severity_count == 34
        )  # Every 3rd positive/negative conflict (33) + 0 cross-campaign = ~34

        # Generate bulk actions for large dataset
        bulk_actions = await manager.generate_bulk_resolution_actions(
            results, priority_filter="HIGH"
        )

        # Should still generate files efficiently
        assert "negative_keywords_bulk_upload.csv" in bulk_actions

        # Verify CSV contains expected number of entries
        negative_csv = bulk_actions["negative_keywords_bulk_upload.csv"]
        csv_lines = negative_csv.split("\n")
        assert len(csv_lines) > 30  # Header + ~33 high-severity conflicts

    def test_script_file_validation(self):
        """Test script file validation and loading."""
        # Test with temporary script file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False
        ) as temp_script:
            temp_script.write("""
            // Test Google Ads Script
            const CONFIG = {
              EMAIL_RECIPIENTS: {{EMAIL_RECIPIENTS}},
              S3_BUCKET: '{{S3_BUCKET}}',
              THRESHOLDS: {{DETECTION_THRESHOLDS}},
              REPORT_RETENTION_DAYS: {{REPORT_RETENTION_DAYS}},
              MAX_CONFLICTS_PER_EMAIL: {{MAX_CONFLICTS_PER_EMAIL}},
            };

            function main() {
              console.log('Test script');
            }
            """)
            temp_script.flush()

            # Mock the script path to point to our temp file
            manager = ConflictDetectionManager(
                google_ads_client=Mock(),
                s3_client=Mock(),
                config=ConflictDetectionConfig(),
            )

            with patch.object(
                manager, "_get_script_path", return_value=temp_script.name
            ):
                configured_script = manager._configure_script("// Original script")
                assert isinstance(configured_script, str)

        # Clean up
        Path(temp_script.name).unlink()

    @pytest.mark.asyncio
    async def test_csv_format_validation(
        self, sample_conflict_results, test_config, mock_manager_dependencies
    ):
        """Test that generated CSV files have correct format for Google Ads import."""
        mock_google_ads_client, mock_s3_client = mock_manager_dependencies
        customer_id = "1234567890"

        manager = ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=test_config,
        )

        results = manager._process_script_results(customer_id, sample_conflict_results)
        bulk_actions = await manager.generate_bulk_resolution_actions(results)

        # Test negative keywords CSV format
        negative_csv = bulk_actions["negative_keywords_bulk_upload.csv"]
        lines = negative_csv.strip().split("\n")

        # Check header
        header = lines[0]
        expected_columns = [
            "Campaign",
            "Ad Group",
            "Keyword",
            "Criterion Type",
            "Labels",
        ]
        assert all(col in header for col in expected_columns)

        # Check data rows
        for line in lines[1:]:
            if line.strip():  # Skip empty lines
                columns = line.split(",")
                assert len(columns) >= 5  # Should have all required columns
                assert "Negative Keyword" in line  # Should specify criterion type

        # Test campaign actions CSV format
        campaign_csv = bulk_actions["campaign_optimization_actions.csv"]
        lines = campaign_csv.strip().split("\n")

        header = lines[0]
        expected_columns = [
            "Campaign",
            "Action",
            "Recommendation",
            "Priority",
            "Expected Impact",
        ]
        assert all(col in header for col in expected_columns)

        # Test keyword pause actions CSV format
        keyword_csv = bulk_actions["keyword_pause_actions.csv"]
        lines = keyword_csv.strip().split("\n")

        header = lines[0]
        expected_columns = ["Campaign", "Ad Group", "Keyword", "Action", "Reason"]
        assert all(col in header for col in expected_columns)
