"""Tests for quarterly data extraction scheduler."""

from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import ScriptConfig, ScriptType
from paidsearchnav_mcp.platforms.google.scripts.quarterly_scheduler import (
    ComprehensiveQuarterlyAuditScript,
    QuarterlyDataExtractionScheduler,
)
from paidsearchnav_mcp.platforms.google.scripts.scheduler import ScriptScheduler


class TestQuarterlyDataExtractionScheduler:
    """Test QuarterlyDataExtractionScheduler functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock script scheduler."""
        scheduler = Mock(spec=ScriptScheduler)
        scheduler.add_schedule = Mock(return_value="schedule_123")
        scheduler.get_all_schedules = Mock(return_value=[])
        return scheduler

    @pytest.fixture
    def quarterly_scheduler(self, mock_client, mock_scheduler):
        """Create QuarterlyDataExtractionScheduler instance."""
        return QuarterlyDataExtractionScheduler(mock_client, mock_scheduler)

    def test_scheduler_initialization(self, quarterly_scheduler):
        """Test scheduler initialization."""
        assert quarterly_scheduler.client is not None
        assert quarterly_scheduler.scheduler is not None
        assert (
            len(quarterly_scheduler.quarterly_schedules) == 5
        )  # 4 regular + 1 comprehensive

    def test_quarterly_schedules_configuration(self, quarterly_scheduler):
        """Test quarterly schedules configuration."""
        schedules = quarterly_scheduler.quarterly_schedules

        # Test search terms daily schedule
        search_terms_config = schedules["search_terms_daily"]
        assert search_terms_config["cron"] == "0 3 * * *"  # Daily at 3 AM
        assert search_terms_config["parameters"]["date_range"] == "YESTERDAY"

        # Test comprehensive quarterly schedule
        comprehensive_config = schedules["comprehensive_quarterly"]
        assert comprehensive_config["cron"] == "0 2 1 */3 *"  # Quarterly
        assert comprehensive_config["parameters"]["comprehensive"] is True

    def test_setup_quarterly_schedules_success(
        self, quarterly_scheduler, mock_scheduler
    ):
        """Test successful setup of quarterly schedules."""
        customer_id = "1234567890"  # Valid 10-digit customer ID

        schedule_ids = quarterly_scheduler.setup_quarterly_schedules(customer_id)

        # Should have created 5 schedules
        assert len(schedule_ids) == 5
        assert all(
            schedule_id == "schedule_123" for schedule_id in schedule_ids.values()
        )

        # Verify scheduler.add_schedule was called for each schedule
        assert (
            mock_scheduler.add_schedule.call_count >= 4
        )  # At least 4 regular schedules

    def test_setup_quarterly_schedules_with_failure(
        self, quarterly_scheduler, mock_scheduler
    ):
        """Test schedule setup with some failures."""
        customer_id = "1234567890"  # Valid 10-digit customer ID

        # Mock scheduler to fail on some schedules
        def mock_add_schedule_with_failure(*args, **kwargs):
            # Check if this is a keywords script by examining the script instance
            script_instance = args[0] if args else None
            if script_instance and hasattr(script_instance, "config"):
                if "keywords" in script_instance.config.name:
                    raise Exception("Schedule setup failed")
            return "schedule_123"

        mock_scheduler.add_schedule.side_effect = mock_add_schedule_with_failure

        schedule_ids = quarterly_scheduler.setup_quarterly_schedules(customer_id)

        # Should have some successful and some failed schedules
        assert len(schedule_ids) == 5
        assert None in schedule_ids.values()  # Some should be None due to failures

    def test_trigger_manual_extraction_search_terms(
        self, quarterly_scheduler, mock_scheduler
    ):
        """Test manual search terms extraction trigger."""
        customer_id = "1234567890"  # Valid 10-digit customer ID
        date_range = "LAST_7_DAYS"

        # Mock the executor
        mock_executor = Mock()
        mock_executor.register_script = Mock(return_value="script_123")
        mock_executor.execute_script = Mock(return_value={"status": "completed"})
        mock_scheduler.executor = mock_executor

        execution_id = quarterly_scheduler.trigger_manual_extraction(
            "search_terms", customer_id, date_range
        )

        assert execution_id == "script_123"
        mock_executor.register_script.assert_called_once()
        mock_executor.execute_script.assert_called_once_with("script_123")

    def test_trigger_manual_extraction_all_scripts(
        self, quarterly_scheduler, mock_scheduler
    ):
        """Test manual extraction of all scripts."""
        customer_id = "1234567890"  # Valid 10-digit customer ID
        date_range = "LAST_30_DAYS"

        # Mock the executor
        mock_executor = Mock()
        mock_executor.register_script = Mock(return_value="comprehensive_script_123")
        mock_executor.execute_script = Mock(return_value={"status": "completed"})
        mock_scheduler.executor = mock_executor

        execution_id = quarterly_scheduler.trigger_manual_extraction(
            "all", customer_id, date_range
        )

        assert execution_id == "comprehensive_script_123"

    def test_trigger_manual_extraction_invalid_type(self, quarterly_scheduler):
        """Test manual extraction with invalid type."""
        customer_id = "1234567890"  # Valid 10-digit customer ID

        execution_id = quarterly_scheduler.trigger_manual_extraction(
            "invalid_type", customer_id
        )

        assert execution_id is None

    def test_get_quarterly_schedule_status(self, quarterly_scheduler):
        """Test getting quarterly schedule status."""
        status = quarterly_scheduler.get_quarterly_schedule_status()

        assert status["schedule_count"] == 5
        assert "schedules" in status
        assert "next_executions" in status
        assert "last_executions" in status

        # Verify schedule information
        schedules = status["schedules"]
        assert "search_terms_daily" in schedules
        assert schedules["search_terms_daily"]["cron"] == "0 3 * * *"

    def test_pause_and_resume_schedules(self, quarterly_scheduler):
        """Test pausing and resuming schedules."""
        # Test pause
        result = quarterly_scheduler.pause_quarterly_schedules()
        assert result is True

        # Test resume
        result = quarterly_scheduler.resume_quarterly_schedules()
        assert result is True

    def test_get_extraction_history(self, quarterly_scheduler, mock_scheduler):
        """Test getting extraction history."""
        # Mock schedule data
        mock_schedules = [
            {
                "schedule_id": "schedule_1",
                "description": "Daily search terms performance extraction",
                "recent_executions": [
                    {
                        "execution_id": "exec_1",
                        "start_time": "2024-01-01T03:00:00",
                        "end_time": "2024-01-01T03:05:00",
                        "status": "completed",
                    }
                ],
            },
            {
                "schedule_id": "schedule_2",
                "description": "Weekly geographic performance extraction",
                "recent_executions": [
                    {
                        "execution_id": "exec_2",
                        "start_time": "2024-01-01T04:00:00",
                        "end_time": "2024-01-01T04:03:00",
                        "status": "completed",
                    }
                ],
            },
        ]

        mock_scheduler.get_all_schedules.return_value = mock_schedules

        history = quarterly_scheduler.get_extraction_history()

        assert len(history) == 2
        assert history[0]["extraction_type"] == "geographic"  # More recent
        assert history[1]["extraction_type"] == "search_terms"

    def test_get_extraction_history_with_filter(
        self, quarterly_scheduler, mock_scheduler
    ):
        """Test getting extraction history with type filter."""
        # Mock schedule data
        mock_schedules = [
            {
                "schedule_id": "schedule_1",
                "description": "Daily search terms performance extraction",
                "recent_executions": [
                    {
                        "execution_id": "exec_1",
                        "start_time": "2024-01-01T03:00:00",
                        "end_time": "2024-01-01T03:05:00",
                        "status": "completed",
                    }
                ],
            },
            {
                "schedule_id": "schedule_2",
                "description": "Weekly geographic performance extraction",
                "recent_executions": [
                    {
                        "execution_id": "exec_2",
                        "start_time": "2024-01-01T04:00:00",
                        "end_time": "2024-01-01T04:03:00",
                        "status": "completed",
                    }
                ],
            },
        ]

        mock_scheduler.get_all_schedules.return_value = mock_schedules

        # Filter for search terms only (using "search terms" which appears in the description)
        history = quarterly_scheduler.get_extraction_history(
            days=30, extraction_type="search terms"
        )

        assert len(history) == 1
        assert history[0]["extraction_type"] == "search_terms"

    def test_extract_type_from_description(self, quarterly_scheduler):
        """Test extraction type detection from description."""
        test_cases = [
            ("Daily search terms performance extraction", "search_terms"),
            ("Weekly keyword performance extraction", "keywords"),
            ("Geographic performance analysis", "geographic"),
            ("Campaign performance monitoring", "campaigns"),
            ("Comprehensive quarterly audit", "comprehensive"),
            ("Unknown script type", "unknown"),
        ]

        for description, expected_type in test_cases:
            result = quarterly_scheduler._extract_type_from_description(description)
            assert result == expected_type

    def test_validate_customer_id_success(self, quarterly_scheduler):
        """Test successful customer ID validation."""
        valid_customer_ids = ["1234567890", "9876543210", "0123456789"]

        for customer_id in valid_customer_ids:
            assert quarterly_scheduler._validate_customer_id(customer_id) is True

    def test_validate_customer_id_failure(self, quarterly_scheduler):
        """Test customer ID validation failures."""
        invalid_customer_ids = [
            "123456789",  # 9 digits
            "12345678901",  # 11 digits
            "abcd123456",  # Contains letters
            "123-456-789",  # Contains dashes
            "",  # Empty string
            None,  # None value
            123,  # Non-string type
        ]

        for customer_id in invalid_customer_ids:
            assert quarterly_scheduler._validate_customer_id(customer_id) is False

    def test_validate_date_range_success(self, quarterly_scheduler):
        """Test successful date range validation."""
        valid_ranges = [
            "TODAY",
            "YESTERDAY",
            "LAST_30_DAYS",
            "LAST_90_DAYS",
            "THIS_MONTH",
            "LAST_QUARTER",
            "2024-01-01,2024-01-31",  # Custom range
            "2023-12-01,2023-12-31",  # Custom range
        ]

        for date_range in valid_ranges:
            assert quarterly_scheduler._validate_date_range(date_range) is True

    def test_validate_date_range_failure(self, quarterly_scheduler):
        """Test date range validation failures."""
        invalid_ranges = [
            "INVALID_RANGE",
            "2024-13-01,2024-13-31",  # Invalid month
            "2024-01-01,2024-02-30",  # Invalid date
            "2024/01/01,2024/01/31",  # Wrong format
            "2024-01-01",  # Missing end date
            "",  # Empty string
            None,  # None value
        ]

        for date_range in invalid_ranges:
            assert quarterly_scheduler._validate_date_range(date_range) is False

    def test_validate_extraction_parameters(self, quarterly_scheduler):
        """Test comprehensive parameter validation."""
        # Test successful validation
        errors = quarterly_scheduler._validate_extraction_parameters(
            "1234567890", "LAST_30_DAYS"
        )
        assert len(errors) == 0

        # Test validation with errors
        errors = quarterly_scheduler._validate_extraction_parameters(
            "invalid", "INVALID_RANGE"
        )
        assert len(errors) == 2
        assert "customer_id" in errors
        assert "date_range" in errors

        # Test partial validation errors
        errors = quarterly_scheduler._validate_extraction_parameters(
            "1234567890", "INVALID_RANGE"
        )
        assert len(errors) == 1
        assert "date_range" in errors
        assert "customer_id" not in errors

    def test_trigger_manual_extraction_with_invalid_parameters(
        self, quarterly_scheduler
    ):
        """Test manual extraction with invalid parameters."""
        execution_id = quarterly_scheduler.trigger_manual_extraction(
            "search_terms", "invalid_customer_id", "INVALID_RANGE"
        )

        assert execution_id is None

    def test_setup_quarterly_schedules_with_invalid_customer_id(
        self, quarterly_scheduler
    ):
        """Test setup with invalid customer ID."""
        schedule_ids = quarterly_scheduler.setup_quarterly_schedules("invalid")

        # All schedules should be None due to validation failure
        assert len(schedule_ids) == 5
        assert all(schedule_id is None for schedule_id in schedule_ids.values())


class TestComprehensiveQuarterlyAuditScript:
    """Test ComprehensiveQuarterlyAuditScript functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def script_config(self):
        """Create script configuration for testing."""
        return ScriptConfig(
            name="comprehensive_audit",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Comprehensive quarterly audit",
            parameters={
                "customer_id": "1234567890",  # Valid 10-digit customer ID
                "date_range": "LAST_90_DAYS",
                "comprehensive": True,
                "run_all_scripts": True,
            },
        )

    @pytest.fixture
    def audit_script(self, mock_client, script_config):
        """Create ComprehensiveQuarterlyAuditScript instance."""
        return ComprehensiveQuarterlyAuditScript(mock_client, script_config)

    def test_script_initialization(self, audit_script):
        """Test comprehensive audit script initialization."""
        assert audit_script.client is not None
        assert audit_script.config.name == "comprehensive_audit"

    def test_required_parameters(self, audit_script):
        """Test required parameters."""
        required_params = audit_script.get_required_parameters()
        assert "customer_id" in required_params
        assert "date_range" in required_params

    def test_parameter_validation_success(self, audit_script):
        """Test successful parameter validation."""
        assert audit_script.validate_parameters() is True

    def test_parameter_validation_failure(self, mock_client):
        """Test parameter validation failure."""
        config = ScriptConfig(
            name="incomplete_audit",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Incomplete audit script",
            parameters={
                # Missing required parameters
                "comprehensive": True,
            },
        )

        script = ComprehensiveQuarterlyAuditScript(mock_client, config)
        assert script.validate_parameters() is False

    def test_generate_script(self, audit_script):
        """Test comprehensive audit script generation."""
        script_code = audit_script.generate_script()

        # Verify script contains expected elements
        assert "function main()" in script_code
        assert "Comprehensive Quarterly Audit Script" in script_code
        assert "totalRows" in script_code
        assert "totalChanges" in script_code
        assert "extraction_results" in script_code

    def test_process_results(self, audit_script):
        """Test comprehensive audit results processing."""
        results = {
            "execution_time": 120.5,
            "rows_processed": 2515,
            "changes_made": 30,
            "extraction_results": {
                "search_terms": {"rows_processed": 1500, "changes_made": 0},
                "keywords": {"rows_processed": 800, "changes_made": 25},
                "geographic": {"rows_processed": 200, "changes_made": 0},
                "campaigns": {"rows_processed": 15, "changes_made": 5},
            },
            "warnings": ["Some manual review items identified"],
        }

        processed = audit_script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["execution_time"] == 120.5
        assert processed["rows_processed"] == 2515
        assert processed["changes_made"] == 30
        assert len(processed["warnings"]) == 1
        assert processed["details"]["script_type"] == "comprehensive_quarterly_audit"
        assert "extraction_results" in processed["details"]


class TestQuarterlySchedulerIntegration:
    """Test integration scenarios for quarterly scheduler."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock script scheduler."""
        scheduler = Mock(spec=ScriptScheduler)
        scheduler.add_schedule = Mock(return_value="schedule_123")
        return scheduler

    def test_end_to_end_schedule_setup(self, mock_client, mock_scheduler):
        """Test end-to-end schedule setup process."""
        quarterly_scheduler = QuarterlyDataExtractionScheduler(
            mock_client, mock_scheduler
        )
        customer_id = "1234567890"  # Valid 10-digit customer ID

        # Setup schedules
        schedule_ids = quarterly_scheduler.setup_quarterly_schedules(customer_id)

        # Verify all schedules were created
        assert len(schedule_ids) == 5
        assert mock_scheduler.add_schedule.call_count >= 4

        # Verify schedule configuration
        calls = mock_scheduler.add_schedule.call_args_list

        # Check that different cron expressions were used
        cron_expressions = []
        for call in calls:
            cron_expr = call[0][1]  # Second argument is cron expression
            cron_expressions.append(cron_expr)

        # Should have both daily and weekly schedules
        assert "0 3 * * *" in cron_expressions  # Daily schedules
        assert "0 4 * * 1" in cron_expressions  # Weekly schedules

    def test_error_recovery_in_setup(self, mock_client, mock_scheduler):
        """Test error recovery during schedule setup."""
        quarterly_scheduler = QuarterlyDataExtractionScheduler(
            mock_client, mock_scheduler
        )
        customer_id = "1234567890"  # Valid 10-digit customer ID

        # Mock partial failures
        call_count = 0

        def failing_add_schedule(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second call
                raise Exception("Simulated failure")
            return f"schedule_{call_count}"

        mock_scheduler.add_schedule.side_effect = failing_add_schedule

        schedule_ids = quarterly_scheduler.setup_quarterly_schedules(customer_id)

        # Should have some successful and some failed schedules
        assert len(schedule_ids) == 5
        successful_schedules = [sid for sid in schedule_ids.values() if sid is not None]
        failed_schedules = [sid for sid in schedule_ids.values() if sid is None]

        assert len(successful_schedules) > 0
        assert len(failed_schedules) > 0

    def test_comprehensive_audit_integration(self, mock_client, mock_scheduler):
        """Test comprehensive audit integration."""
        quarterly_scheduler = QuarterlyDataExtractionScheduler(
            mock_client, mock_scheduler
        )

        # Mock executor for comprehensive audit
        mock_executor = Mock()
        mock_executor.register_script = Mock(return_value="comprehensive_123")
        mock_executor.execute_script = Mock(
            return_value={
                "success": True,
                "rows_processed": 2515,
                "changes_made": 30,
                "extraction_results": {
                    "search_terms": {"rows_processed": 1500, "changes_made": 0},
                    "keywords": {"rows_processed": 800, "changes_made": 25},
                    "geographic": {"rows_processed": 200, "changes_made": 0},
                    "campaigns": {"rows_processed": 15, "changes_made": 5},
                },
            }
        )
        mock_scheduler.executor = mock_executor

        # Trigger comprehensive extraction
        execution_id = quarterly_scheduler.trigger_manual_extraction(
            "all",
            "1234567890",
            "LAST_90_DAYS",  # Valid 10-digit customer ID
        )

        assert execution_id == "comprehensive_123"
        mock_executor.register_script.assert_called_once()

        # Verify the script that was registered is comprehensive audit script
        registered_script = mock_executor.register_script.call_args[0][0]
        assert isinstance(registered_script, ComprehensiveQuarterlyAuditScript)
        assert registered_script.config.parameters["comprehensive"] is True
