"""Unit tests for workflow step executors."""

from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.orchestration.step_executors import (
    AnalysisEngineExecutor,
    BaseStepExecutor,
    CustomerInitServiceExecutor,
    DefaultStepExecutor,
    GoogleAdsClientExecutor,
    NotificationServiceExecutor,
    ReportGeneratorExecutor,
    S3FileServiceExecutor,
    StepExecutorRegistry,
)


class TestStepExecutorRegistry:
    """Test step executor registry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = StepExecutorRegistry()

    def test_registry_initialization(self):
        """Test registry is initialized with default executors."""
        services = self.registry.list_services()

        expected_services = [
            "customer_init_service",
            "s3_file_service",
            "google_ads_client",
            "analysis_engine",
            "report_generator",
            "notification_service",
            "default",
        ]

        for service in expected_services:
            assert service in services
            assert self.registry.has_executor(service)

    def test_register_custom_executor(self):
        """Test registering a custom executor."""

        class CustomExecutor(BaseStepExecutor):
            async def execute(self, context):
                return {"custom": True}

        self.registry.register("custom_service", CustomExecutor)

        assert self.registry.has_executor("custom_service")
        executor = self.registry.get_executor("custom_service")
        assert isinstance(executor, CustomExecutor)

    def test_unregister_executor(self):
        """Test unregistering an executor."""
        assert self.registry.has_executor("default")

        self.registry.unregister("default")

        assert not self.registry.has_executor("default")
        assert self.registry.get_executor("default") is None

    def test_get_nonexistent_executor(self):
        """Test getting a non-existent executor."""
        executor = self.registry.get_executor("nonexistent")
        assert executor is None


class TestDefaultStepExecutor:
    """Test default step executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = DefaultStepExecutor()

    @pytest.mark.asyncio
    async def test_execute_noop(self):
        """Test executing no-op operation."""
        context = {
            "customer_id": "test_customer",
            "step_config": {"config": {"operation": "noop"}},
        }

        result = await self.executor.execute(context)

        assert result["customer_id"] == "test_customer"
        assert result["result"]["status"] == "completed"
        assert result["result"]["operation"] == "noop"

    @pytest.mark.asyncio
    async def test_execute_with_delay(self):
        """Test executing with delay."""
        context = {
            "customer_id": "test_customer",
            "step_config": {"config": {"delay": 0.1, "operation": "test"}},
        }

        result = await self.executor.execute(context)

        assert result["customer_id"] == "test_customer"
        assert result["result"]["status"] == "completed"
        assert result["result"]["operation"] == "test"

    def test_get_timeout(self):
        """Test getting timeout from step config."""
        step_config = {"timeout": 600}
        assert self.executor.get_timeout(step_config) == 600

        # Test default timeout
        assert self.executor.get_timeout({}) == 300


@patch("paidsearchnav.orchestration.step_executors.CustomerInitializationService")
class TestCustomerInitServiceExecutor:
    """Test customer initialization service executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = CustomerInitServiceExecutor()
        self.settings = Settings()

    @pytest.mark.asyncio
    async def test_execute_customer_init(self, mock_service_class):
        """Test executing customer initialization."""
        # Mock the service
        mock_service = AsyncMock()
        mock_service.initialize_customer.return_value = {
            "s3_folder_path": "s3://bucket/customer_123",
            "status": "initialized",
        }
        mock_service_class.return_value = mock_service

        context = {
            "customer_id": "customer_123",
            "step_config": {
                "config": {
                    "customer_name": "Test Customer",
                    "google_ads_customer_id": "1234567890",
                }
            },
            "settings": self.settings,
        }

        result = await self.executor.execute(context)

        assert result["customer_initialized"] is True
        assert result["customer_id"] == "customer_123"
        assert result["s3_folder_path"] == "s3://bucket/customer_123"
        assert result["initialization_details"]["status"] == "initialized"

        # Verify service was called correctly
        mock_service.initialize_customer.assert_called_once_with(
            customer_id="customer_123",
            customer_name="Test Customer",
            google_ads_customer_id="1234567890",
        )


@patch("paidsearchnav.orchestration.step_executors.FileManager")
class TestS3FileServiceExecutor:
    """Test S3 file service executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = S3FileServiceExecutor()
        self.settings = Settings()

    @pytest.mark.asyncio
    async def test_execute_setup_structure(self, mock_file_manager_class):
        """Test executing S3 structure setup."""
        # Mock the file manager
        mock_file_manager = AsyncMock()
        mock_file_manager.setup_customer_structure.return_value = {
            "folders_created": ["input", "output", "reports"]
        }
        mock_file_manager_class.return_value = mock_file_manager

        context = {
            "customer_id": "customer_123",
            "step_config": {"config": {"operation": "setup_structure"}},
            "settings": self.settings,
        }

        result = await self.executor.execute(context)

        assert result["operation"] == "setup_structure"
        assert result["customer_id"] == "customer_123"
        assert result["result"]["folders_created"] == ["input", "output", "reports"]

        mock_file_manager.setup_customer_structure.assert_called_once_with(
            "customer_123"
        )

    @pytest.mark.asyncio
    async def test_execute_unknown_operation(self, mock_file_manager_class):
        """Test executing unknown operation raises error."""
        mock_file_manager = AsyncMock()
        mock_file_manager_class.return_value = mock_file_manager

        context = {
            "customer_id": "customer_123",
            "step_config": {"config": {"operation": "unknown_operation"}},
            "settings": self.settings,
        }

        with pytest.raises(ValueError, match="Unknown S3 operation: unknown_operation"):
            await self.executor.execute(context)


@patch("paidsearchnav.orchestration.step_executors.GoogleAdsClient")
class TestGoogleAdsClientExecutor:
    """Test Google Ads client executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = GoogleAdsClientExecutor()
        self.settings = Settings()

    @pytest.mark.asyncio
    async def test_execute_verify_access(self, mock_client_class):
        """Test executing Google Ads access verification."""
        # Mock the client
        mock_client = AsyncMock()
        mock_client.verify_customer_access.return_value = {
            "access_granted": True,
            "account_name": "Test Account",
        }
        mock_client_class.return_value = mock_client

        context = {
            "customer_id": "customer_123",
            "step_config": {"config": {"operation": "verify_access"}},
            "settings": self.settings,
        }

        result = await self.executor.execute(context)

        assert result["operation"] == "verify_access"
        assert result["customer_id"] == "customer_123"
        assert result["result"]["access_granted"] is True

        mock_client.verify_customer_access.assert_called_once_with("customer_123")


@patch("paidsearchnav.orchestration.step_executors.keyword_analyzer")
@patch("paidsearchnav.orchestration.step_executors.search_term_analyzer")
class TestAnalysisEngineExecutor:
    """Test analysis engine executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = AnalysisEngineExecutor()
        self.settings = Settings()

    @pytest.mark.asyncio
    async def test_execute_multiple_analyzers(
        self, mock_search_term_analyzer, mock_keyword_analyzer
    ):
        """Test executing multiple analyzers."""
        # Mock analyzers
        mock_keyword = AsyncMock()
        mock_keyword.analyze_customer.return_value = {"keywords_analyzed": 100}
        mock_keyword_analyzer.KeywordAnalyzer.return_value = mock_keyword

        mock_search_term = AsyncMock()
        mock_search_term.analyze_customer.return_value = {"search_terms_analyzed": 200}
        mock_search_term_analyzer.SearchTermAnalyzer.return_value = mock_search_term

        context = {
            "customer_id": "customer_123",
            "step_config": {"config": {"analyzers": ["keyword_match", "search_terms"]}},
            "settings": self.settings,
        }

        result = await self.executor.execute(context)

        assert result["customer_id"] == "customer_123"
        assert result["analyzers_run"] == ["keyword_match", "search_terms"]
        assert result["results"]["keyword_match"]["keywords_analyzed"] == 100
        assert result["results"]["search_terms"]["search_terms_analyzed"] == 200


@patch("paidsearchnav.orchestration.step_executors.ReportGenerator")
class TestReportGeneratorExecutor:
    """Test report generator executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = ReportGeneratorExecutor()
        self.settings = Settings()

    @pytest.mark.asyncio
    async def test_execute_multiple_reports(self, mock_report_generator_class):
        """Test executing multiple report generations."""
        # Mock the report generator
        mock_generator = AsyncMock()
        mock_generator.generate_report.return_value = {
            "report_path": "s3://bucket/reports/test.html",
            "size": 1024,
        }
        mock_report_generator_class.return_value = mock_generator

        context = {
            "customer_id": "customer_123",
            "step_config": {
                "config": {"report_types": ["summary", "detailed"], "formats": ["html"]}
            },
            "settings": self.settings,
        }

        result = await self.executor.execute(context)

        assert result["customer_id"] == "customer_123"
        assert "summary_html" in result["reports_generated"]
        assert "detailed_html" in result["reports_generated"]
        assert result["results"]["summary_html"]["size"] == 1024

        # Verify generator was called for each report type
        assert mock_generator.generate_report.call_count == 2


class TestNotificationServiceExecutor:
    """Test notification service executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = NotificationServiceExecutor()

    @pytest.mark.asyncio
    async def test_execute_notification(self):
        """Test executing notification."""
        context = {
            "customer_id": "customer_123",
            "step_config": {
                "config": {
                    "type": "completion",
                    "recipients": ["test@example.com"],
                    "message": "Workflow completed successfully",
                }
            },
        }

        result = await self.executor.execute(context)

        assert result["customer_id"] == "customer_123"
        assert result["notification_type"] == "completion"
        assert result["recipients"] == ["test@example.com"]
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_execute_notification_defaults(self):
        """Test executing notification with default values."""
        context = {"customer_id": "customer_123", "step_config": {"config": {}}}

        result = await self.executor.execute(context)

        assert result["customer_id"] == "customer_123"
        assert result["notification_type"] == "completion"
        assert result["recipients"] == []
        assert result["status"] == "sent"


class TestBaseStepExecutor:
    """Test base step executor functionality."""

    def test_get_timeout_default(self):
        """Test getting default timeout."""

        class TestExecutor(BaseStepExecutor):
            async def execute(self, context):
                return {}

        executor = TestExecutor()
        assert executor.get_timeout({}) == 300

    def test_get_timeout_from_config(self):
        """Test getting timeout from config."""

        class TestExecutor(BaseStepExecutor):
            async def execute(self, context):
                return {}

        executor = TestExecutor()
        step_config = {"timeout": 600}
        assert executor.get_timeout(step_config) == 600

    def test_validate_config_default(self):
        """Test default config validation."""

        class TestExecutor(BaseStepExecutor):
            async def execute(self, context):
                return {}

        executor = TestExecutor()
        assert executor.validate_config({"test": "config"}) is True
