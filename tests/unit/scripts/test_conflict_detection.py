"""
Tests for Google Ads Scripts Conflict Detection System

Test coverage for conflict detection functionality, result processing,
and bulk action generation.

Based on PaidSearchNav Issue #464
"""

import os
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav_mcp.core.exceptions import ConflictDetectionError, DataProcessingError
from paidsearchnav_mcp.scripts.conflict_detection import (
    ConflictDetectionConfig,
    ConflictDetectionManager,
    ConflictDetectionResults,
    ConflictRecord,
    create_conflict_detection_manager,
    run_conflict_detection_for_customer,
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


class TestConflictDetectionConfig:
    """Test conflict detection configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConflictDetectionConfig()

        assert config.email_recipients == ["alerts@paidsearchnav.com"]
        assert config.s3_bucket == "paidsearchnav-conflict-reports"
        assert config.detection_thresholds["min_clicks_for_analysis"] == 5
        assert config.detection_thresholds["high_cost_threshold"] == 25.0
        assert config.detection_thresholds["quality_score_threshold"] == 4
        assert config.detection_thresholds["bid_competition_threshold"] == 0.10
        assert config.report_retention_days == 90
        assert config.max_conflicts_per_email == 50

    def test_custom_config(self):
        """Test custom configuration values."""
        custom_config = ConflictDetectionConfig(
            email_recipients=["test@example.com", "admin@example.com"],
            s3_bucket="test-bucket",
            detection_thresholds={
                "min_clicks_for_analysis": 10,
                "high_cost_threshold": 50.0,
                "quality_score_threshold": 5,
                "bid_competition_threshold": 0.15,
            },
            report_retention_days=60,
            max_conflicts_per_email=25,
        )

        assert custom_config.email_recipients == [
            "test@example.com",
            "admin@example.com",
        ]
        assert custom_config.s3_bucket == "test-bucket"
        assert custom_config.detection_thresholds["min_clicks_for_analysis"] == 10
        assert custom_config.detection_thresholds["high_cost_threshold"] == 50.0
        assert custom_config.report_retention_days == 60
        assert custom_config.max_conflicts_per_email == 25


class TestConflictRecord:
    """Test conflict record model."""

    def test_conflict_record_creation(self):
        """Test creating a conflict record."""
        conflict = ConflictRecord(
            type="POSITIVE_NEGATIVE_CONFLICT",
            severity="HIGH",
            campaign="Test Campaign",
            ad_group="Test Ad Group",
            keyword="fitness connection dallas",
            issue="Conflicts with negative keyword: dallas",
            estimated_impact={"wastedSpend": 150.50},
            detected_at=datetime.now(),
        )

        assert conflict.type == "POSITIVE_NEGATIVE_CONFLICT"
        assert conflict.severity == "HIGH"
        assert conflict.campaign == "Test Campaign"
        assert conflict.ad_group == "Test Ad Group"
        assert conflict.keyword == "fitness connection dallas"
        assert conflict.issue == "Conflicts with negative keyword: dallas"
        assert conflict.estimated_impact["wastedSpend"] == 150.50
        assert conflict.resolution_status == "PENDING"  # default value

    def test_conflict_record_minimal(self):
        """Test creating a conflict record with minimal data."""
        conflict = ConflictRecord(
            type="CROSS_CAMPAIGN_CONFLICT",
            severity="MEDIUM",
            campaign="Campaign 1; Campaign 2",
            issue="Competing across multiple campaigns",
            detected_at=datetime.now(),
        )

        assert conflict.type == "CROSS_CAMPAIGN_CONFLICT"
        assert conflict.severity == "MEDIUM"
        assert conflict.campaign == "Campaign 1; Campaign 2"
        assert conflict.ad_group is None
        assert conflict.keyword is None
        assert conflict.estimated_impact == {}
        assert conflict.resolution_status == "PENDING"


class TestConflictDetectionResults:
    """Test conflict detection results model."""

    def test_results_creation(self):
        """Test creating conflict detection results."""
        conflicts = [
            ConflictRecord(
                type="POSITIVE_NEGATIVE_CONFLICT",
                severity="HIGH",
                campaign="Test Campaign",
                issue="Test conflict",
                detected_at=datetime.now(),
            )
        ]

        results = ConflictDetectionResults(
            timestamp=datetime.now(),
            account_id="1234567890",
            positive_negative_conflicts=conflicts,
            total_conflicts=1,
            high_severity_count=1,
            estimated_monthly_loss=150.0,
        )

        assert results.account_id == "1234567890"
        assert len(results.positive_negative_conflicts) == 1
        assert results.total_conflicts == 1
        assert results.high_severity_count == 1
        assert results.estimated_monthly_loss == 150.0
        assert len(results.cross_campaign_conflicts) == 0
        assert len(results.functionality_issues) == 0
        assert len(results.geographic_conflicts) == 0


class TestConflictDetectionManager:
    """Test conflict detection manager."""

    @pytest.fixture
    def mock_google_ads_client(self):
        """Mock Google Ads client."""
        return Mock()

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client."""
        return Mock()

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return ConflictDetectionConfig(
            email_recipients=["test@example.com"], s3_bucket="test-bucket"
        )

    @pytest.fixture
    def manager(self, mock_google_ads_client, mock_s3_client, config):
        """Test manager instance."""
        return ConflictDetectionManager(
            google_ads_client=mock_google_ads_client,
            s3_client=mock_s3_client,
            config=config,
        )

    def test_manager_initialization(self, manager, config):
        """Test manager initialization."""
        assert manager.config == config
        assert manager.google_ads_client is not None
        assert manager.s3_client is not None

    @pytest.mark.asyncio
    async def test_deploy_script_success(self, manager, mock_env_vars):
        """Test successful script deployment."""
        customer_id = "1234567890"

        # Mock script content with template markers
        script_content = """
        const CONFIG = {
            EMAIL_RECIPIENTS: {{EMAIL_RECIPIENTS}},
            S3_BUCKET: '{{S3_BUCKET}}',
            THRESHOLDS: {{DETECTION_THRESHOLDS}},
            REPORT_RETENTION_DAYS: {{REPORT_RETENTION_DAYS}},
            MAX_CONFLICTS_PER_EMAIL: {{MAX_CONFLICTS_PER_EMAIL}},
        };
        """

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                script_content
            )

            with patch.object(
                manager, "_deploy_script_via_api", return_value="script_123"
            ) as mock_deploy:
                script_id = await manager.deploy_conflict_detection_script(customer_id)

                assert script_id == "script_123"
                mock_deploy.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_script_file_not_found(self, manager):
        """Test script deployment with missing script file."""
        customer_id = "1234567890"

        with patch.object(
            manager,
            "_get_script_path",
            side_effect=ConflictDetectionError("Script not found"),
        ):
            with pytest.raises(
                ConflictDetectionError, match="Script deployment failed"
            ):
                await manager.deploy_conflict_detection_script(customer_id)

    @pytest.mark.asyncio
    async def test_run_conflict_detection_success(self, manager, mock_env_vars):
        """Test successful conflict detection run."""
        customer_id = "1234567890"

        # Mock the internal methods
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
                    with patch.object(manager, "_store_results"):
                        with patch.object(manager, "_send_conflict_alerts"):
                            results = await manager.run_conflict_detection(customer_id)

                            assert isinstance(results, ConflictDetectionResults)
                            assert results.account_id == customer_id
                            assert results.total_conflicts == 0

    @pytest.mark.asyncio
    async def test_run_conflict_detection_with_conflicts(self, manager, mock_env_vars):
        """Test conflict detection run with detected conflicts."""
        customer_id = "1234567890"

        mock_results_data = {
            "timestamp": datetime.now().isoformat(),
            "positiveNegativeConflicts": [
                {
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "severity": "HIGH",
                    "keyword": "fitness connection dallas",
                    "keywordMatchType": "EXACT",
                    "negativeKeyword": "dallas",
                    "negativeMatchType": "BROAD",
                    "campaign": "Test Campaign",
                    "adGroup": "Test Ad Group",
                    "estimatedImpact": {"wastedSpend": 150.50},
                    "detectedAt": datetime.now().isoformat(),
                }
            ],
            "crossCampaignConflicts": [],
            "functionalityIssues": [],
            "geographicConflicts": [],
        }

        with patch.object(
            manager, "deploy_conflict_detection_script", return_value="script_123"
        ):
            with patch.object(manager, "_execute_script", return_value="exec_456"):
                with patch.object(
                    manager, "_wait_for_results", return_value=mock_results_data
                ):
                    with patch.object(manager, "_store_results"):
                        with patch.object(
                            manager, "_send_conflict_alerts"
                        ) as mock_alerts:
                            results = await manager.run_conflict_detection(customer_id)

                            assert results.total_conflicts == 1
                            assert results.high_severity_count == 1
                            assert len(results.positive_negative_conflicts) == 1

                            # Should send alerts for high-severity conflicts
                            mock_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_bulk_resolution_actions(self, manager):
        """Test bulk resolution action generation."""
        # Create test results with various conflict types
        positive_negative_conflict = ConflictRecord(
            type="POSITIVE_NEGATIVE_CONFLICT",
            severity="HIGH",
            campaign="Test Campaign",
            ad_group="Test Ad Group",
            keyword="fitness connection dallas",
            issue="Conflicts with negative keyword: dallas",
            detected_at=datetime.now(),
        )

        cross_campaign_conflict = ConflictRecord(
            type="CROSS_CAMPAIGN_CONFLICT",
            severity="MEDIUM",
            campaign="Campaign 1; Campaign 2",
            keyword="gym near me",
            issue="Competing across multiple campaigns",
            detected_at=datetime.now(),
        )

        results = ConflictDetectionResults(
            timestamp=datetime.now(),
            account_id="1234567890",
            positive_negative_conflicts=[positive_negative_conflict],
            cross_campaign_conflicts=[cross_campaign_conflict],
            total_conflicts=2,
            high_severity_count=1,
            estimated_monthly_loss=200.0,
        )

        with patch.object(manager, "_store_bulk_actions"):
            bulk_actions = await manager.generate_bulk_resolution_actions(
                results, priority_filter="HIGH"
            )

            # Should generate negative keywords file for high-priority positive/negative conflicts
            assert "negative_keywords_bulk_upload.csv" in bulk_actions

            # Check CSV content
            negative_csv = bulk_actions["negative_keywords_bulk_upload.csv"]
            assert "fitness connection dallas" in negative_csv
            assert "Negative Keyword" in negative_csv

    def test_filter_conflicts_by_priority(self, manager):
        """Test filtering conflicts by priority level."""
        high_conflict = ConflictRecord(
            type="POSITIVE_NEGATIVE_CONFLICT",
            severity="HIGH",
            campaign="Test Campaign",
            issue="High severity conflict",
            detected_at=datetime.now(),
        )

        medium_conflict = ConflictRecord(
            type="CROSS_CAMPAIGN_CONFLICT",
            severity="MEDIUM",
            campaign="Test Campaign",
            issue="Medium severity conflict",
            detected_at=datetime.now(),
        )

        low_conflict = ConflictRecord(
            type="GEOGRAPHIC_CONFLICT",
            severity="LOW",
            campaign="Test Campaign",
            issue="Low severity conflict",
            detected_at=datetime.now(),
        )

        results = ConflictDetectionResults(
            timestamp=datetime.now(),
            account_id="1234567890",
            positive_negative_conflicts=[high_conflict],
            cross_campaign_conflicts=[medium_conflict],
            geographic_conflicts=[low_conflict],
            total_conflicts=3,
            high_severity_count=1,
            estimated_monthly_loss=100.0,
        )

        # Test HIGH filter
        high_filtered = manager._filter_conflicts_by_priority(results, "HIGH")
        assert len(high_filtered["positive_negative"]) == 1
        assert len(high_filtered["cross_campaign"]) == 0
        assert len(high_filtered["geographic"]) == 0
        assert len(high_filtered["all_high_severity"]) == 1

        # Test MEDIUM filter
        medium_filtered = manager._filter_conflicts_by_priority(results, "MEDIUM")
        assert len(medium_filtered["positive_negative"]) == 0
        assert len(medium_filtered["cross_campaign"]) == 1
        assert len(medium_filtered["geographic"]) == 0

        # Test no filter (all conflicts)
        all_filtered = manager._filter_conflicts_by_priority(results, None)
        assert len(all_filtered["positive_negative"]) == 1
        assert len(all_filtered["cross_campaign"]) == 1
        assert len(all_filtered["geographic"]) == 1

    def test_generate_negative_keywords_bulk_action(self, manager):
        """Test negative keywords bulk action CSV generation."""
        conflicts = [
            ConflictRecord(
                type="POSITIVE_NEGATIVE_CONFLICT",
                severity="HIGH",
                campaign="Test Campaign 1",
                keyword="fitness connection dallas",
                issue="Conflicts with negative keyword",
                detected_at=datetime.now(),
            ),
            ConflictRecord(
                type="POSITIVE_NEGATIVE_CONFLICT",
                severity="MEDIUM",
                campaign="Test Campaign 2",
                keyword="gym near me",
                issue="Conflicts with negative keyword",
                detected_at=datetime.now(),
            ),
            ConflictRecord(
                type="POSITIVE_NEGATIVE_CONFLICT",
                severity="LOW",
                campaign="Test Campaign 3",
                keyword="low priority keyword",
                issue="Conflicts with negative keyword",
                detected_at=datetime.now(),
            ),
        ]

        csv_content = manager._generate_negative_keywords_bulk_action(conflicts)

        assert csv_content is not None
        assert "Campaign,Ad Group,Keyword,Criterion Type,Labels" in csv_content
        assert '"fitness connection dallas"' in csv_content
        assert '"gym near me"' in csv_content
        assert "Negative Keyword" in csv_content
        assert "Conflict Resolution - Automated" in csv_content

        # Low severity conflicts should now be included
        assert '"low priority keyword"' in csv_content

    def test_generate_negative_keywords_no_conflicts(self, manager):
        """Test negative keywords generation with no conflicts."""
        csv_content = manager._generate_negative_keywords_bulk_action([])
        assert csv_content is None

    def test_generate_campaign_actions(self, manager):
        """Test campaign actions CSV generation."""
        conflicts = [
            ConflictRecord(
                type="CROSS_CAMPAIGN_CONFLICT",
                severity="HIGH",
                campaign="Campaign 1; Campaign 2",
                keyword="competing keyword",
                issue="Competing across multiple campaigns",
                detected_at=datetime.now(),
            ),
            ConflictRecord(
                type="LANDING_PAGE_ISSUE",
                severity="MEDIUM",
                campaign="Test Campaign",
                issue="Landing page is not accessible",
                detected_at=datetime.now(),
            ),
        ]

        csv_content = manager._generate_campaign_actions(conflicts)

        assert csv_content is not None
        assert "Campaign,Action,Recommendation,Priority,Expected Impact" in csv_content
        assert "Review Keyword Competition" in csv_content
        assert "Fix Campaign Settings" in csv_content
        assert "competing keyword" in csv_content
        assert "Landing page is not accessible" in csv_content

    def test_generate_keyword_pause_actions(self, manager):
        """Test keyword pause actions CSV generation."""
        high_severity_conflicts = [
            ConflictRecord(
                type="POSITIVE_NEGATIVE_CONFLICT",
                severity="HIGH",
                campaign="Test Campaign",
                ad_group="Test Ad Group",
                keyword="problematic keyword",
                issue="High-severity conflict",
                detected_at=datetime.now(),
            ),
            ConflictRecord(
                type="CROSS_CAMPAIGN_CONFLICT",
                severity="HIGH",
                campaign="Test Campaign",
                keyword="another problematic keyword",
                issue="Another high-severity conflict",
                detected_at=datetime.now(),
            ),
        ]

        csv_content = manager._generate_keyword_pause_actions(high_severity_conflicts)

        assert csv_content is not None
        assert "Campaign,Ad Group,Keyword,Action,Reason" in csv_content
        assert "problematic keyword" in csv_content
        assert "another problematic keyword" in csv_content
        assert "Pause" in csv_content
        assert "High-severity conflict" in csv_content

    def test_process_script_results(self, manager):
        """Test processing of raw script results."""
        raw_results = {
            "timestamp": "2024-08-19T10:00:00Z",
            "positiveNegativeConflicts": [
                {
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "severity": "HIGH",
                    "keyword": "fitness connection dallas",
                    "keywordMatchType": "EXACT",
                    "negativeKeyword": "dallas",
                    "negativeMatchType": "BROAD",
                    "campaign": "Test Campaign",
                    "adGroup": "Test Ad Group",
                    "estimatedImpact": {"wastedSpend": 150.50},
                    "detectedAt": "2024-08-19T10:00:00Z",
                }
            ],
            "crossCampaignConflicts": [
                {
                    "type": "CROSS_CAMPAIGN_CONFLICT",
                    "severity": "MEDIUM",
                    "keyword": "gym near me",
                    "campaigns": [{"name": "Campaign 1"}, {"name": "Campaign 2"}],
                    "estimatedWastedSpend": 89.30,
                    "detectedAt": "2024-08-19T10:00:00Z",
                }
            ],
            "functionalityIssues": [],
            "geographicConflicts": [],
        }

        results = manager._process_script_results("1234567890", raw_results)

        assert isinstance(results, ConflictDetectionResults)
        assert results.account_id == "1234567890"
        assert results.total_conflicts == 2
        assert results.high_severity_count == 1
        assert len(results.positive_negative_conflicts) == 1
        assert len(results.cross_campaign_conflicts) == 1

        # Check positive/negative conflict processing
        pn_conflict = results.positive_negative_conflicts[0]
        assert pn_conflict.type == "POSITIVE_NEGATIVE_CONFLICT"
        assert pn_conflict.severity == "HIGH"
        assert pn_conflict.keyword == "fitness connection dallas"
        assert "dallas" in pn_conflict.issue

        # Check cross-campaign conflict processing
        cc_conflict = results.cross_campaign_conflicts[0]
        assert cc_conflict.type == "CROSS_CAMPAIGN_CONFLICT"
        assert cc_conflict.severity == "MEDIUM"
        assert cc_conflict.keyword == "gym near me"
        assert "campaigns" in cc_conflict.issue


class TestUtilityFunctions:
    """Test utility functions."""

    def test_create_conflict_detection_manager(self):
        """Test manager creation utility function."""
        with patch(
            "paidsearchnav.integrations.google_ads_write_client.GoogleAdsWriteClient"
        ):
            with patch("paidsearchnav.integrations.s3.S3Client"):
                manager = create_conflict_detection_manager("1234567890")

                assert isinstance(manager, ConflictDetectionManager)
                assert isinstance(manager.config, ConflictDetectionConfig)

    @pytest.mark.asyncio
    async def test_run_conflict_detection_for_customer(self):
        """Test customer-specific conflict detection utility function."""
        customer_id = "1234567890"

        with patch(
            "paidsearchnav.scripts.conflict_detection.create_conflict_detection_manager"
        ) as mock_create:
            mock_manager = Mock()
            mock_results = ConflictDetectionResults(
                timestamp=datetime.now(),
                account_id=customer_id,
                total_conflicts=0,
                high_severity_count=0,
                estimated_monthly_loss=0.0,
            )
            mock_manager.run_conflict_detection = AsyncMock(return_value=mock_results)
            mock_create.return_value = mock_manager

            results = await run_conflict_detection_for_customer(customer_id)

            assert results == mock_results
            mock_manager.run_conflict_detection.assert_called_once_with(customer_id)


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def manager(self):
        """Test manager with mocked dependencies."""
        return ConflictDetectionManager(
            google_ads_client=Mock(), s3_client=Mock(), config=ConflictDetectionConfig()
        )

    @pytest.mark.asyncio
    async def test_deploy_script_error_handling(self, manager):
        """Test error handling in script deployment."""
        with patch.object(
            manager, "_get_script_path", side_effect=Exception("File system error")
        ):
            with pytest.raises(
                ConflictDetectionError, match="Script deployment failed"
            ):
                await manager.deploy_conflict_detection_script("1234567890")

    @pytest.mark.asyncio
    async def test_run_conflict_detection_error_handling(self, manager):
        """Test error handling in conflict detection."""
        with patch.object(
            manager,
            "deploy_conflict_detection_script",
            side_effect=Exception("Deployment failed"),
        ):
            with pytest.raises(
                ConflictDetectionError, match="Conflict detection failed"
            ):
                await manager.run_conflict_detection("1234567890")

    @pytest.mark.asyncio
    async def test_generate_bulk_actions_error_handling(self, manager):
        """Test error handling in bulk action generation."""
        results = ConflictDetectionResults(
            timestamp=datetime.now(),
            account_id="1234567890",
            total_conflicts=0,
            high_severity_count=0,
            estimated_monthly_loss=0.0,
        )

        with patch.object(
            manager, "_store_bulk_actions", side_effect=Exception("Storage error")
        ):
            # Storage errors should not prevent bulk action generation
            # The method should complete successfully even if storage fails
            bulk_actions = await manager.generate_bulk_resolution_actions(results)
            assert isinstance(bulk_actions, dict)

    def test_process_script_results_malformed_data(self, manager):
        """Test error handling with malformed script results."""
        malformed_results = {
            "timestamp": "invalid-timestamp",
            "positiveNegativeConflicts": [
                {
                    # Missing required fields
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "detectedAt": "invalid-timestamp",
                }
            ],
        }

        with pytest.raises(DataProcessingError, match="Results processing failed"):
            manager._process_script_results("1234567890", malformed_results)


class TestConfigurationScenarios:
    """Test various configuration scenarios."""

    def test_email_configuration(self):
        """Test email recipient configuration."""
        config = ConflictDetectionConfig(
            email_recipients=["admin@example.com", "alerts@example.com"]
        )

        assert len(config.email_recipients) == 2
        assert "admin@example.com" in config.email_recipients
        assert "alerts@example.com" in config.email_recipients

    def test_threshold_configuration(self):
        """Test detection threshold configuration."""
        config = ConflictDetectionConfig(
            detection_thresholds={
                "min_clicks_for_analysis": 20,
                "high_cost_threshold": 100.0,
                "quality_score_threshold": 6,
                "bid_competition_threshold": 0.25,
            }
        )

        assert config.detection_thresholds["min_clicks_for_analysis"] == 20
        assert config.detection_thresholds["high_cost_threshold"] == 100.0
        assert config.detection_thresholds["quality_score_threshold"] == 6
        assert config.detection_thresholds["bid_competition_threshold"] == 0.25

    def test_s3_bucket_configuration(self):
        """Test S3 bucket configuration."""
        config = ConflictDetectionConfig(s3_bucket="custom-conflict-reports-bucket")

        assert config.s3_bucket == "custom-conflict-reports-bucket"

    def test_retention_configuration(self):
        """Test report retention configuration."""
        config = ConflictDetectionConfig(
            report_retention_days=120, max_conflicts_per_email=100
        )

        assert config.report_retention_days == 120
        assert config.max_conflicts_per_email == 100
