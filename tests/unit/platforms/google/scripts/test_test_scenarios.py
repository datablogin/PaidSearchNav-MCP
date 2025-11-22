"""Tests for Google Ads Scripts test scenarios."""

import tempfile
from pathlib import Path

from paidsearchnav_mcp.platforms.google.scripts.test_scenarios import (
    ConflictDetectionTestCase,
    EndToEndAccuracyScenario,
    GeographicPerformanceTestCase,
    LocalIntentTestCase,
    MockConflictDetectionScript,
    MockDataExtractionScript,
    MockLocalIntentScript,
    MockPerformanceMaxScript,
    MultiLocationPerformanceScenario,
    PerformanceMaxTestCase,
    ScaleAndPerformanceScenario,
    ScalePerformanceTestCase,
)
from paidsearchnav_mcp.platforms.google.scripts.testing_framework import (
    ScriptScriptTestCaseConfig,
    ScriptScriptTestDataManager,
    ScriptScriptTestResult,
    ScriptScriptTestSeverity,
    ScriptScriptTestStatus,
)


class TestMockScripts:
    """Test mock script implementations."""

    def test_mock_data_extraction_script(self):
        """Test mock data extraction script."""
        script = MockDataExtractionScript()

        # Test script generation
        script_code = script.generate_script()
        assert isinstance(script_code, str)
        assert "Mock data extraction" in script_code

        # Test result processing
        results = {"data": [{"keyword": "test", "clicks": 100}]}
        processed = script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["rows_processed"] == 1
        assert processed["execution_time"] > 0

    def test_mock_conflict_detection_script(self):
        """Test mock conflict detection script."""
        script = MockConflictDetectionScript()

        script_code = script.generate_script()
        assert isinstance(script_code, str)
        assert "Mock conflict detection" in script_code

        results = {"conflicts": [{"type": "location_conflict"}]}
        processed = script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["rows_processed"] == 1

    def test_mock_performance_max_script(self):
        """Test mock Performance Max script."""
        script = MockPerformanceMaxScript()

        script_code = script.generate_script()
        assert isinstance(script_code, str)
        assert "Mock Performance Max" in script_code

        results = {"analyzed_campaigns": [{"campaign_id": "test"}]}
        processed = script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["rows_processed"] == 1

    def test_mock_local_intent_script(self):
        """Test mock local intent script."""
        script = MockLocalIntentScript()

        script_code = script.generate_script()
        assert isinstance(script_code, str)
        assert "Mock local intent" in script_code

        results = {"classified_terms": [{"search_term": "gym near me"}]}
        processed = script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["rows_processed"] == 1


class TestEndToEndAccuracyScenario:
    """Test end-to-end accuracy scenario implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.scenario = EndToEndAccuracyScenario(self.data_manager)

    def test_create_test_cases_structure(self):
        """Test that all required test cases are created."""
        test_cases = self.scenario.create_test_cases()

        assert len(test_cases) == 4

        # Verify each test case type exists
        test_types = [type(tc) for tc in test_cases]
        from paidsearchnav.platforms.google.scripts.testing_framework import (
            DataAccuracyTestCase,
        )

        assert any(isinstance(tc, DataAccuracyTestCase) for tc in test_cases)
        assert any(isinstance(tc, ConflictDetectionTestCase) for tc in test_cases)
        assert any(isinstance(tc, PerformanceMaxTestCase) for tc in test_cases)
        assert any(isinstance(tc, LocalIntentTestCase) for tc in test_cases)

    def test_data_extraction_test_config(self):
        """Test data extraction test configuration."""
        test_cases = self.scenario.create_test_cases()
        data_extraction_test = next(
            tc
            for tc in test_cases
            if tc.config.name == "fitness_connection_data_extraction_accuracy"
        )

        assert data_extraction_test.config.severity == ScriptScriptTestSeverity.CRITICAL
        assert data_extraction_test.config.timeout_seconds == 600
        assert data_extraction_test.config.expected_results["min_accuracy"] == 0.999

    def test_conflict_detection_test_config(self):
        """Test conflict detection test configuration."""
        test_cases = self.scenario.create_test_cases()
        conflict_test = next(
            tc
            for tc in test_cases
            if tc.config.name == "fitness_connection_conflict_detection"
        )

        assert conflict_test.config.severity == ScriptScriptTestSeverity.HIGH
        assert conflict_test.config.expected_results["min_accuracy"] == 0.995
        assert conflict_test.config.expected_results["max_false_positives"] == 0.02


class TestMultiLocationPerformanceScenario:
    """Test multi-location performance scenario."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.scenario = MultiLocationPerformanceScenario(self.data_manager)

    def test_create_geographic_test_cases(self):
        """Test geographic performance test case creation."""
        test_cases = self.scenario.create_test_cases()

        assert len(test_cases) == 1
        assert isinstance(test_cases[0], GeographicPerformanceTestCase)

        geo_test = test_cases[0]
        assert geo_test.config.name == "dallas_san_antonio_geographic_optimization"
        assert geo_test.config.expected_results["local_conversion_improvement"] == 0.25


class TestScaleAndPerformanceScenario:
    """Test scale and performance scenario."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.scenario = ScaleAndPerformanceScenario(self.data_manager)

    def test_create_scale_test_cases(self):
        """Test scale performance test case creation."""
        test_cases = self.scenario.create_test_cases()

        assert len(test_cases) == 3

        # Verify different keyword counts
        keyword_counts = [tc.config.parameters["keyword_count"] for tc in test_cases]
        assert 100 in keyword_counts
        assert 1000 in keyword_counts
        assert 10000 in keyword_counts

    def test_small_account_configuration(self):
        """Test small account test configuration."""
        test_cases = self.scenario.create_test_cases()
        small_test = next(
            tc for tc in test_cases if tc.config.parameters["keyword_count"] == 100
        )

        assert small_test.config.name == "small_account_performance_100_keywords"
        assert small_test.config.expected_results["execution_time_max"] == 30.0
        assert small_test.config.expected_results["accuracy_min"] == 0.99

    def test_large_account_configuration(self):
        """Test large account test configuration."""
        test_cases = self.scenario.create_test_cases()
        large_test = next(
            tc for tc in test_cases if tc.config.parameters["keyword_count"] == 10000
        )

        assert large_test.config.name == "large_account_performance_10000_keywords"
        assert large_test.config.expected_results["execution_time_max"] == 600.0
        assert large_test.config.severity == ScriptScriptTestSeverity.HIGH


class TestConflictDetectionTestCase:
    """Test conflict detection test case implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.mock_script = MockConflictDetectionScript()

        self.config = ScriptScriptTestCaseConfig(
            name="test_conflict_detection",
            description="Test conflict detection",
            test_type="conflict_detection",
            severity=ScriptScriptTestSeverity.HIGH,
            expected_results={"min_accuracy": 0.995, "max_false_positives": 0.02},
        )

    def test_generate_known_conflicts(self):
        """Test generation of known conflicts."""
        test_case = ConflictDetectionTestCase(
            self.config, self.data_manager, self.mock_script
        )

        # Load test data
        test_data = self.data_manager.load_fitness_connection_data()
        conflicts = test_case._generate_known_conflicts(test_data)

        assert len(conflicts) > 0

        # Verify conflict structure
        first_conflict = conflicts[0]
        assert first_conflict["type"] == "location_conflict"
        assert "keyword1" in first_conflict
        assert "keyword2" in first_conflict
        assert "location1" in first_conflict
        assert "location2" in first_conflict
        assert first_conflict["location1"] != first_conflict["location2"]

    def test_execute_conflict_detection(self):
        """Test conflict detection execution."""
        test_case = ConflictDetectionTestCase(
            self.config, self.data_manager, self.mock_script
        )

        # Load test data and generate conflicts
        test_data = self.data_manager.load_fitness_connection_data()
        results = test_case._execute_conflict_detection(test_data)

        assert "conflicts" in results
        assert len(results["conflicts"]) > 0

    def test_validate_conflict_detection(self):
        """Test conflict detection validation."""
        test_case = ConflictDetectionTestCase(
            self.config, self.data_manager, self.mock_script
        )

        # Create sample known conflicts and detected conflicts
        known_conflicts = [
            {"type": "location_conflict", "keyword1": "gym", "keyword2": "fitness"},
            {
                "type": "location_conflict",
                "keyword1": "workout",
                "keyword2": "exercise",
            },
        ]

        script_results = {
            "conflicts": [
                {"type": "location_conflict", "keyword1": "gym", "keyword2": "fitness"},
                {"type": "false_positive", "keyword1": "false", "keyword2": "positive"},
            ]
        }

        validation_results = test_case._validate_conflict_detection(
            known_conflicts, script_results
        )

        assert "detection_accuracy" in validation_results
        assert "false_positive_rate" in validation_results
        assert validation_results["true_positives"] == 1
        assert validation_results["false_positives"] == 1

    def test_full_execution(self):
        """Test full conflict detection test execution."""
        test_case = ConflictDetectionTestCase(
            self.config, self.data_manager, self.mock_script
        )

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_conflict_detection"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "conflict_detection" in result.metrics
        assert result.execution_time > 0


class TestPerformanceMaxTestCase:
    """Test Performance Max test case implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.mock_script = MockPerformanceMaxScript()

        self.config = ScriptScriptTestCaseConfig(
            name="test_performance_max",
            description="Test Performance Max analysis",
            test_type="performance_max",
            severity=ScriptScriptTestSeverity.HIGH,
            expected_results={
                "min_accuracy": 0.999,
                "geographic_attribution_accuracy": 0.95,
            },
        )

    def test_load_performance_max_data(self):
        """Test loading Performance Max test data."""
        test_case = PerformanceMaxTestCase(
            self.config, self.data_manager, self.mock_script
        )

        test_data = test_case._load_performance_max_data()

        assert "campaigns" in test_data
        assert "asset_performance" in test_data
        assert len(test_data["campaigns"]) == 2
        assert len(test_data["asset_performance"]) == 2

        # Verify campaign structure
        campaign = test_data["campaigns"][0]
        required_fields = [
            "campaign_id",
            "name",
            "budget",
            "target_roas",
            "conversions",
            "cost",
            "location",
        ]
        for field in required_fields:
            assert field in campaign

    def test_execute_performance_max_analysis(self):
        """Test Performance Max analysis execution."""
        test_case = PerformanceMaxTestCase(
            self.config, self.data_manager, self.mock_script
        )

        test_data = test_case._load_performance_max_data()
        results = test_case._execute_performance_max_analysis(test_data)

        assert "analyzed_campaigns" in results
        assert len(results["analyzed_campaigns"]) == 2

        # Verify analysis structure
        analyzed = results["analyzed_campaigns"][0]
        assert "actual_roas" in analyzed
        assert "target_roas" in analyzed
        assert "performance_status" in analyzed
        assert "location" in analyzed

    def test_validate_performance_max_results(self):
        """Test Performance Max results validation."""
        test_case = PerformanceMaxTestCase(
            self.config, self.data_manager, self.mock_script
        )

        test_data = test_case._load_performance_max_data()
        script_results = test_case._execute_performance_max_analysis(test_data)

        validation_results = test_case._validate_performance_max_results(
            test_data, script_results
        )

        assert "metric_accuracy" in validation_results
        assert "geographic_attribution_accuracy" in validation_results
        assert validation_results["metric_accuracy"] >= 0.0
        assert validation_results["geographic_attribution_accuracy"] >= 0.0

    def test_full_execution(self):
        """Test full Performance Max test execution."""
        test_case = PerformanceMaxTestCase(
            self.config, self.data_manager, self.mock_script
        )

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_performance_max"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "performance_analysis" in result.metrics


class TestLocalIntentTestCase:
    """Test local intent test case implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)
        self.mock_script = MockLocalIntentScript()

        self.config = ScriptScriptTestCaseConfig(
            name="test_local_intent",
            description="Test local intent classification",
            test_type="local_intent",
            severity=ScriptScriptTestSeverity.MEDIUM,
            expected_results={"min_accuracy": 0.95, "near_me_detection": 0.98},
        )

    def test_execute_local_intent_classification(self):
        """Test local intent classification execution."""
        test_case = LocalIntentTestCase(
            self.config, self.data_manager, self.mock_script
        )

        # Create sample search terms
        search_terms = [
            {"search_term": "gym near me", "local_intent": True},
            {"search_term": "fitness center nearby", "local_intent": True},
            {"search_term": "best workout routines", "local_intent": False},
        ]

        results = test_case._execute_local_intent_classification(search_terms)

        assert "classified_terms" in results
        assert len(results["classified_terms"]) == 3

        # Verify classification structure
        classified = results["classified_terms"][0]
        assert "search_term" in classified
        assert "predicted_local_intent" in classified
        assert "confidence" in classified
        assert "indicators_found" in classified

    def test_validate_local_intent_results(self):
        """Test local intent results validation."""
        test_case = LocalIntentTestCase(
            self.config, self.data_manager, self.mock_script
        )

        actual_terms = [
            {"search_term": "gym near me", "local_intent": True},
            {"search_term": "best workout routines", "local_intent": False},
        ]

        script_results = {
            "classified_terms": [
                {"predicted_local_intent": True, "confidence": 0.95},
                {"predicted_local_intent": False, "confidence": 0.85},
            ]
        }

        validation_results = test_case._validate_local_intent_results(
            actual_terms, script_results
        )

        assert "overall_accuracy" in validation_results
        assert "near_me_accuracy" in validation_results
        assert validation_results["overall_accuracy"] == 1.0  # Perfect classification
        assert validation_results["correct_classifications"] == 2

    def test_near_me_detection_accuracy(self):
        """Test specific 'near me' detection accuracy."""
        test_case = LocalIntentTestCase(
            self.config, self.data_manager, self.mock_script
        )

        actual_terms = [
            {"search_term": "gym near me", "local_intent": True},
            {"search_term": "restaurant near me", "local_intent": True},
        ]

        script_results = {
            "classified_terms": [
                {"predicted_local_intent": True, "confidence": 0.95},
                {"predicted_local_intent": True, "confidence": 0.98},
            ]
        }

        validation_results = test_case._validate_local_intent_results(
            actual_terms, script_results
        )

        assert validation_results["near_me_accuracy"] == 1.0
        assert validation_results["near_me_total"] == 2
        assert validation_results["near_me_correct"] == 2

    def test_full_execution(self):
        """Test full local intent test execution."""
        test_case = LocalIntentTestCase(
            self.config, self.data_manager, self.mock_script
        )

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_local_intent"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "local_intent_classification" in result.metrics


class TestGeographicPerformanceTestCase:
    """Test geographic performance test case implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)

        self.config = ScriptScriptTestCaseConfig(
            name="test_geographic_performance",
            description="Test geographic performance optimization",
            test_type="geographic_performance",
            severity=ScriptScriptTestSeverity.HIGH,
            expected_results={
                "local_conversion_improvement": 0.25,
                "geographic_targeting_efficiency": 0.35,
            },
        )

    def test_simulate_geographic_optimization(self):
        """Test geographic optimization simulation."""
        test_case = GeographicPerformanceTestCase(self.config, self.data_manager)

        # Load Fitness Connection data
        fitness_data = self.data_manager.load_fitness_connection_data()

        optimization_results = test_case._simulate_geographic_optimization(fitness_data)

        assert "location_results" in optimization_results
        location_results = optimization_results["location_results"]

        # Should have results for each location
        assert len(location_results) == 2  # Dallas and San Antonio

        # Verify result structure
        for location_result in location_results.values():
            assert "baseline_conversion_rate" in location_result
            assert "optimized_conversion_rate" in location_result
            assert "improvement_factor" in location_result
            assert (
                location_result["improvement_factor"] > 1.0
            )  # Should show improvement

    def test_calculate_performance_improvements(self):
        """Test performance improvement calculations."""
        test_case = GeographicPerformanceTestCase(self.config, self.data_manager)

        baseline = {"baseline_local_conversion_rate": 0.035}

        optimization = {
            "location_results": {
                "Location1": {
                    "improvement_factor": 1.25,
                    "baseline_conversion_rate": 0.035,
                    "optimized_conversion_rate": 0.044,
                },
                "Location2": {
                    "improvement_factor": 1.30,
                    "baseline_conversion_rate": 0.035,
                    "optimized_conversion_rate": 0.046,
                },
            }
        }

        performance_metrics = test_case._calculate_performance_improvements(
            baseline, optimization
        )

        assert "local_conversion_improvement" in performance_metrics
        assert "geographic_targeting_efficiency" in performance_metrics
        assert performance_metrics["location_count"] == 2
        assert (
            performance_metrics["local_conversion_improvement"] > 0.20
        )  # Should show significant improvement

    def test_full_execution(self):
        """Test full geographic performance test execution."""
        test_case = GeographicPerformanceTestCase(self.config, self.data_manager)

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_geographic_performance"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "local_conversion_optimization" in result.metrics
        assert "geographic_targeting_efficiency" in result.metrics


class TestScalePerformanceTestCase:
    """Test scale performance test case implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_path = Path(tempfile.mkdtemp())
        self.data_manager = ScriptScriptTestDataManager(self.test_data_path)

        self.config = ScriptScriptTestCaseConfig(
            name="test_scale_performance",
            description="Test scale performance",
            test_type="scale_performance",
            severity=ScriptScriptTestSeverity.MEDIUM,
            parameters={"keyword_count": 1000},
            expected_results={
                "execution_time_max": 120.0,
                "accuracy_min": 0.99,
                "error_rate_max": 0.01,
            },
        )

    def test_generate_scale_test_data(self):
        """Test scale test data generation."""
        test_case = ScalePerformanceTestCase(self.config, self.data_manager)

        test_data = test_case._generate_scale_test_data(1000)

        assert "keywords" in test_data
        assert len(test_data["keywords"]) == 1000

        # Verify keyword structure
        keyword = test_data["keywords"][0]
        required_fields = [
            "keyword_id",
            "keyword",
            "clicks",
            "impressions",
            "cost",
            "conversions",
        ]
        for field in required_fields:
            assert field in keyword

    def test_simulate_processing(self):
        """Test processing simulation."""
        test_case = ScalePerformanceTestCase(self.config, self.data_manager)

        test_data = test_case._generate_scale_test_data(100)
        processing_results = test_case._simulate_processing(test_data)

        assert "execution_time" in processing_results
        assert "processed_count" in processing_results
        assert "processed_correctly" in processing_results
        assert "error_count" in processing_results

        assert processing_results["processed_count"] == 100
        assert processing_results["execution_time"] > 0

    def test_validate_scale_performance(self):
        """Test scale performance validation."""
        test_case = ScalePerformanceTestCase(self.config, self.data_manager)

        processing_results = {
            "execution_time": 5.0,
            "processed_count": 1000,
            "processed_correctly": 995,
            "error_count": 5,
        }

        validation_results = test_case._validate_scale_performance(processing_results)

        assert "execution_time" in validation_results
        assert "accuracy" in validation_results
        assert "error_rate" in validation_results
        assert "throughput" in validation_results

        assert validation_results["accuracy"] == 0.995
        assert validation_results["error_rate"] == 0.005
        assert validation_results["throughput"] == 200.0  # 1000/5.0

    def test_full_execution(self):
        """Test full scale performance test execution."""
        test_case = ScalePerformanceTestCase(self.config, self.data_manager)

        result = test_case.execute()

        assert isinstance(result, ScriptScriptTestResult)
        assert result.test_name == "test_scale_performance"
        assert result.status in [
            ScriptScriptTestStatus.PASSED,
            ScriptScriptTestStatus.FAILED,
        ]
        assert "execution_time" in result.metrics
        assert "accuracy" in result.metrics
        assert "throughput" in result.metrics
