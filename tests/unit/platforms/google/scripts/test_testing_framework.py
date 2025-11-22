"""Tests for the Google Ads Scripts testing framework."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from paidsearchnav_mcp.platforms.google.scripts.test_scenarios import (
    ConflictDetectionTestCase,
    EndToEndAccuracyScenario,
    GeographicPerformanceTestCase,
    MockDataExtractionScript,
    MultiLocationPerformanceScenario,
    ScaleAndPerformanceScenario,
)
from paidsearchnav_mcp.platforms.google.scripts.testing_framework import (
    BaseTestCase,
    DataAccuracyTestCase,
    IntegrationTestCase,
    KPIValidationSystem,
    PerformanceEfficiencyTestCase,
    ScriptScriptTestCaseConfig,
    ScriptScriptTestDataManager,
    ScriptScriptTestResult,
    ScriptScriptTestSeverity,
    ScriptScriptTestStatus,
    TestingFramework,
    ValidationMetric,
)


class TestScriptScriptTestDataManager:
    """Test ScriptScriptTestDataManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.manager = ScriptScriptTestDataManager(self.test_data_path)

    def test_load_fitness_connection_data(self):
        """Test loading Fitness Connection test data."""
        data = self.manager.load_fitness_connection_data()

        assert "keywords" in data
        assert "search_terms" in data
        assert "locations" in data
        assert "performance_data" in data

        # Verify data structure
        assert len(data["keywords"]) == 3000
        assert len(data["search_terms"]) == 1000
        assert len(data["locations"]) == 2

        # Verify location data
        locations = data["locations"]
        location_names = [loc["name"] for loc in locations]
        assert "Dallas - Downtown" in location_names
        assert "San Antonio - Riverwalk" in location_names

    def test_load_cotton_patch_data(self):
        """Test loading Cotton Patch test data."""
        data = self.manager.load_cotton_patch_data()

        assert "keywords" in data
        assert "search_terms" in data
        assert "locations" in data
        assert "performance_data" in data

        # Verify data structure
        assert len(data["keywords"]) == 800
        assert len(data["search_terms"]) == 400
        assert len(data["locations"]) == 2

    def test_fitness_keywords_structure(self):
        """Test Fitness Connection keywords data structure."""
        data = self.manager.load_fitness_connection_data()
        keywords = data["keywords"]

        # Test first keyword structure
        first_keyword = keywords[0]
        required_fields = [
            "keyword_id",
            "keyword",
            "match_type",
            "location",
            "clicks",
            "impressions",
            "cost",
            "conversions",
        ]

        for field in required_fields:
            assert field in first_keyword

        # Test data variety
        locations = set(kw["location"] for kw in keywords)
        assert "Dallas" in locations
        assert "San Antonio" in locations

    def test_search_terms_local_intent(self):
        """Test search terms local intent classification."""
        data = self.manager.load_fitness_connection_data()
        search_terms = data["search_terms"]

        local_intent_terms = [
            term for term in search_terms if term.get("local_intent", False)
        ]

        # Should have approximately 33% local intent
        local_intent_ratio = len(local_intent_terms) / len(search_terms)
        assert 0.25 <= local_intent_ratio <= 0.4


class TestKPIValidationSystem:
    """Test KPI validation system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.kpi_system = KPIValidationSystem()

    def test_initialize_kpi_thresholds(self):
        """Test KPI threshold initialization."""
        thresholds = self.kpi_system.thresholds

        assert ValidationMetric.DATA_ACCURACY in thresholds
        assert ValidationMetric.CONFLICT_DETECTION in thresholds
        assert ValidationMetric.TIME_REDUCTION in thresholds

        # Test specific threshold values
        data_accuracy_threshold = thresholds[ValidationMetric.DATA_ACCURACY]
        assert data_accuracy_threshold.target_value == 99.9
        assert data_accuracy_threshold.minimum_value == 99.5

    def test_validate_kpi_success(self):
        """Test successful KPI validation."""
        # Test data accuracy at target
        is_valid, message = self.kpi_system.validate_kpi(
            ValidationMetric.DATA_ACCURACY, 99.9
        )
        assert is_valid
        assert "meets target" in message

    def test_validate_kpi_below_minimum(self):
        """Test KPI validation below minimum threshold."""
        is_valid, message = self.kpi_system.validate_kpi(
            ValidationMetric.DATA_ACCURACY, 98.0
        )
        assert not is_valid
        assert "below minimum" in message

    def test_validate_kpi_above_minimum_below_target(self):
        """Test KPI validation above minimum but below target."""
        is_valid, message = self.kpi_system.validate_kpi(
            ValidationMetric.DATA_ACCURACY, 99.7
        )
        assert is_valid
        assert "above minimum but below target" in message

    def test_record_metrics(self):
        """Test recording KPI metrics."""
        metrics = {
            ValidationMetric.DATA_ACCURACY: 99.8,
            ValidationMetric.TIME_REDUCTION: 85.0,
        }

        self.kpi_system.record_metrics(metrics)

        assert len(self.kpi_system.metrics_history) == 1

        record = self.kpi_system.metrics_history[0]
        assert record["metrics"]["data_accuracy"] == 99.8
        assert record["metrics"]["time_reduction"] == 85.0

    def test_get_metrics_summary_no_data(self):
        """Test metrics summary with no data."""
        summary = self.kpi_system.get_metrics_summary()
        assert summary["status"] == "no_data"

    def test_get_metrics_summary_with_data(self):
        """Test metrics summary with data."""
        # Record passing metrics
        metrics = {
            ValidationMetric.DATA_ACCURACY: 99.9,
            ValidationMetric.TIME_REDUCTION: 85.0,
        }
        self.kpi_system.record_metrics(metrics)

        summary = self.kpi_system.get_metrics_summary()

        assert summary["overall_status"] == "passing"
        assert "data_accuracy" in summary["metrics"]
        assert summary["metrics"]["data_accuracy"]["status"] == "pass"

    def test_get_metrics_summary_with_failures(self):
        """Test metrics summary with failing metrics."""
        # Record failing metrics
        metrics = {
            ValidationMetric.DATA_ACCURACY: 98.0,  # Below minimum
            ValidationMetric.TIME_REDUCTION: 85.0,  # Above target
        }
        self.kpi_system.record_metrics(metrics)

        summary = self.kpi_system.get_metrics_summary()

        assert summary["overall_status"] == "failing"
        assert "data_accuracy" in summary["failed_metrics"]


class TestDataAccuracyTestCase:
    """Test data accuracy test case."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.mock_script = MockDataExtractionScript()

        self.config = ScriptScriptTestCaseConfig(
            name="test_data_accuracy",
            description="Test data accuracy validation",
            test_type="data_accuracy",
            severity=ScriptScriptTestSeverity.CRITICAL,
            expected_results={"min_accuracy": 0.99},
            validation_metrics=[ValidationMetric.DATA_ACCURACY],
        )

    def test_data_accuracy_test_execution(self):
        """Test data accuracy test case execution."""
        test_case = DataAccuracyTestCase(
            self.config, self.data_manager, self.mock_script
        )

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_data_accuracy"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert result.execution_time > 0
        assert "accuracy_score" in result.metrics

    def test_data_accuracy_high_accuracy(self):
        """Test data accuracy test with high accuracy."""
        # Mock high accuracy scenario
        test_case = DataAccuracyTestCase(
            self.config, self.data_manager, self.mock_script
        )

        with patch.object(test_case, "_compare_data_accuracy") as mock_compare:
            mock_compare.return_value = {"overall_accuracy": 0.999}

            result = test_case.execute()

            assert result.status == ScriptScriptTestStatus.PASSED
            assert "accuracy_score" in result.metrics
            assert result.metrics["accuracy_score"] >= 0.99

    def test_data_accuracy_low_accuracy(self):
        """Test data accuracy test with low accuracy."""
        test_case = DataAccuracyTestCase(
            self.config, self.data_manager, self.mock_script
        )

        with patch.object(test_case, "_compare_data_accuracy") as mock_compare:
            mock_compare.return_value = {"overall_accuracy": 0.95}

            result = test_case.execute()

            assert result.status == ScriptScriptTestStatus.FAILED
            assert "below threshold" in result.message


class TestPerformanceEfficiencyTestCase:
    """Test performance efficiency test case."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)

        self.config = ScriptScriptTestCaseConfig(
            name="test_performance_efficiency",
            description="Test performance efficiency",
            test_type="performance",
            severity=ScriptScriptTestSeverity.HIGH,
            expected_results={"time_reduction": 0.8},
        )

    def test_performance_test_execution(self):
        """Test performance efficiency test execution."""
        test_case = PerformanceEfficiencyTestCase(self.config, self.data_manager)

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_performance_efficiency"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.WARNING,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "time_reduction" in result.metrics


class TestIntegrationTestCase:
    """Test integration test case."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)

        self.config = ScriptScriptTestCaseConfig(
            name="test_integration",
            description="Test integration compatibility",
            test_type="integration",
            severity=ScriptScriptTestSeverity.HIGH,
        )

    def test_integration_test_execution(self):
        """Test integration test execution."""
        test_case = IntegrationTestCase(self.config, self.data_manager)

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_integration"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]

        # Verify integration metrics
        expected_metrics = [
            "s3_compatibility",
            "csv_compatibility",
            "bulk_actions_compatibility",
        ]
        for metric in expected_metrics:
            assert metric in result.metrics


class TestTestingFramework:
    """Test main testing framework."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.framework = TestingFramework(self.test_data_path)

    def test_framework_initialization(self):
        """Test framework initialization."""
        assert isinstance(self.framework.data_manager, ScriptScriptTestDataManager)
        assert isinstance(self.framework.kpi_system, KPIValidationSystem)
        assert len(self.framework.test_results) == 0

    def test_run_empty_test_suite(self):
        """Test running empty test suite."""
        result = self.framework.run_test_suite([])

        assert result["execution_summary"]["total_tests"] == 0
        assert result["execution_summary"]["success_rate"] == 0.0

    def test_run_test_suite_with_tests(self):
        """Test running test suite with test cases."""
        # Create mock test cases
        config1 = ScriptScriptTestCaseConfig(
            name="test1",
            description="Test 1",
            test_type="mock",
            severity=ScriptScriptTestSeverity.LOW,
        )

        config2 = ScriptScriptTestCaseConfig(
            name="test2",
            description="Test 2",
            test_type="mock",
            severity=ScriptScriptTestSeverity.MEDIUM,
        )

        mock_test1 = MockTestCase(config1, self.framework.data_manager)
        mock_test2 = MockTestCase(config2, self.framework.data_manager)

        result = self.framework.run_test_suite([mock_test1, mock_test2])

        assert result["execution_summary"]["total_tests"] == 2
        assert len(result["test_results"]) == 2

    def test_generate_report(self):
        """Test report generation."""
        # Add some test results
        test_result = ScriptScriptTestResult(
            test_name="sample_test",
            status=ScriptScriptTestStatus.PASSED,
            execution_time=1.5,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            message="Test passed",
            metrics={"accuracy": 99.5},
        )

        self.framework.test_results.append(test_result)

        # Generate report
        report_path = self.test_data_path / "test_report.json"
        self.framework.generate_report(report_path)

        assert report_path.exists()

        # Verify report content
        with open(report_path) as f:
            report_data = json.load(f)

        assert "report_metadata" in report_data
        assert "test_results" in report_data
        assert len(report_data["test_results"]) == 1

    def test_clear_results(self):
        """Test clearing results and metrics."""
        # Add test data
        test_result = ScriptScriptTestResult(
            test_name="test",
            status=ScriptScriptTestStatus.PASSED,
            execution_time=1.0,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            message="Test",
        )

        self.framework.test_results.append(test_result)
        self.framework.kpi_system.record_metrics({ValidationMetric.DATA_ACCURACY: 99.0})

        # Clear results
        self.framework.clear_results()

        assert len(self.framework.test_results) == 0
        assert len(self.framework.kpi_system.metrics_history) == 0


class TestEndToEndAccuracyScenario:
    """Test end-to-end accuracy scenario."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.scenario = EndToEndAccuracyScenario(self.data_manager)

    def test_create_test_cases(self):
        """Test creation of end-to-end test cases."""
        test_cases = self.scenario.create_test_cases()

        assert len(test_cases) == 4

        # Verify test case types
        test_names = [tc.config.name for tc in test_cases]
        assert "fitness_connection_data_extraction_accuracy" in test_names
        assert "fitness_connection_conflict_detection" in test_names
        assert "performance_max_analysis_accuracy" in test_names
        assert "local_intent_classification_accuracy" in test_names

    def test_data_extraction_test_case(self):
        """Test data extraction accuracy test case."""
        test_cases = self.scenario.create_test_cases()
        data_extraction_test = test_cases[0]

        assert isinstance(data_extraction_test, DataAccuracyTestCase)
        assert data_extraction_test.config.severity == ScriptScriptTestSeverity.CRITICAL
        assert (
            ValidationMetric.DATA_ACCURACY
            in data_extraction_test.config.validation_metrics
        )


class TestMultiLocationPerformanceScenario:
    """Test multi-location performance scenario."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.scenario = MultiLocationPerformanceScenario(self.data_manager)

    def test_create_test_cases(self):
        """Test creation of multi-location test cases."""
        test_cases = self.scenario.create_test_cases()

        assert len(test_cases) == 1
        assert isinstance(test_cases[0], GeographicPerformanceTestCase)

    def test_geographic_performance_test(self):
        """Test geographic performance test case."""
        test_cases = self.scenario.create_test_cases()
        geo_test = test_cases[0]

        result = geo_test.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "dallas_san_antonio_geographic_optimization"
        assert "local_conversion_optimization" in result.metrics


class TestScaleAndPerformanceScenario:
    """Test scale and performance scenario."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.scenario = ScaleAndPerformanceScenario(self.data_manager)

    def test_create_test_cases(self):
        """Test creation of scale and performance test cases."""
        test_cases = self.scenario.create_test_cases()

        assert len(test_cases) == 3

        # Verify different scales
        keyword_counts = [
            tc.config.parameters.get("keyword_count") for tc in test_cases
        ]
        assert 100 in keyword_counts
        assert 1000 in keyword_counts
        assert 10000 in keyword_counts

    def test_small_scale_performance(self):
        """Test small scale performance test."""
        test_cases = self.scenario.create_test_cases()
        small_scale_test = [
            tc for tc in test_cases if tc.config.parameters.get("keyword_count") == 100
        ][0]

        result = small_scale_test.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "execution_time" in result.metrics
        assert "throughput" in result.metrics


class TestConflictDetectionTestCase:
    """Test conflict detection test case."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.mock_script = Mock()

        self.config = ScriptScriptTestCaseConfig(
            name="test_conflict_detection",
            description="Test conflict detection",
            test_type="conflict_detection",
            severity=ScriptScriptTestSeverity.HIGH,
            expected_results={"min_accuracy": 0.995, "max_false_positives": 0.02},
        )

    def test_conflict_detection_execution(self):
        """Test conflict detection test execution."""
        test_case = ConflictDetectionTestCase(
            self.config, self.data_manager, self.mock_script
        )

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_conflict_detection"
        assert "conflict_detection" in result.metrics

    def test_generate_known_conflicts(self):
        """Test generation of known conflicts."""
        test_case = ConflictDetectionTestCase(
            self.config, self.data_manager, self.mock_script
        )
        test_data = self.data_manager.load_fitness_connection_data()

        conflicts = test_case._generate_known_conflicts(test_data)

        assert len(conflicts) > 0
        assert all("type" in conflict for conflict in conflicts)
        assert all("location1" in conflict for conflict in conflicts)
        assert all("location2" in conflict for conflict in conflicts)


# Mock classes for testing


class MockTestCase(BaseTestCase):
    """Mock test case for testing framework."""

    def execute(self) -> ScriptScriptTestResult:
        """Execute mock test."""
        start_time = datetime.utcnow()

        # Simulate test execution
        import time

        time.sleep(0.1)

        execution_time = (datetime.utcnow() - start_time).total_seconds()

        return self._create_test_result(
            status=ScriptScriptTestStatus.PASSED,
            message="Mock test passed",
            execution_time=execution_time,
            start_time=start_time,
            metrics={"mock_metric": 95.0},
        )
