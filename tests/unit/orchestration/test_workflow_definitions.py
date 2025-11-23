"""Unit tests for workflow definition parser and validator."""

import pytest
import yaml

from paidsearchnav_mcp.orchestration.workflow_definitions import (
    ParsedWorkflowDefinition,
    WorkflowDefinitionParser,
    WorkflowStep,
)


class TestWorkflowDefinitionParser:
    """Test workflow definition parser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = WorkflowDefinitionParser()

    def test_parse_valid_yaml_definition(self):
        """Test parsing a valid YAML workflow definition."""
        yaml_content = """
name: "test_workflow"
version: "1.0"
description: "Test workflow"

steps:
  - name: "step1"
    service: "default"
    timeout: 300
    retry: 2
    config:
      test: true

  - name: "step2"
    service: "customer_init_service"
    depends_on: ["step1"]
    timeout: 180
"""

        parsed = self.parser.parse_yaml(yaml_content)

        assert parsed.name == "test_workflow"
        assert parsed.version == "1.0"
        assert parsed.description == "Test workflow"
        assert len(parsed.steps) == 2

        step1 = parsed.steps[0]
        assert step1.name == "step1"
        assert step1.service == "default"
        assert step1.timeout == 300
        assert step1.retry == 2
        assert step1.config == {"test": True}

        step2 = parsed.steps[1]
        assert step2.name == "step2"
        assert step2.service == "customer_init_service"
        assert step2.depends_on == ["step1"]
        assert step2.timeout == 180

    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML."""
        invalid_yaml = """
name: "test_workflow
version: 1.0
steps: [
"""

        with pytest.raises(ValueError, match="Invalid YAML"):
            self.parser.parse_yaml(invalid_yaml)

    def test_validate_definition_missing_required_fields(self):
        """Test validation with missing required fields."""
        # Missing name
        definition = {
            "version": "1.0",
            "steps": [{"name": "step1", "service": "default"}],
        }

        assert not self.parser.validate_definition(definition)
        assert "Missing required field: name" in self.parser.validation_errors

        # Missing version
        definition = {
            "name": "test",
            "steps": [{"name": "step1", "service": "default"}],
        }

        self.parser.validation_errors = []
        assert not self.parser.validate_definition(definition)
        assert "Missing required field: version" in self.parser.validation_errors

        # Missing steps
        definition = {"name": "test", "version": "1.0"}

        self.parser.validation_errors = []
        assert not self.parser.validate_definition(definition)
        assert "Missing required field: steps" in self.parser.validation_errors

    def test_validate_definition_empty_steps(self):
        """Test validation with empty steps."""
        definition = {"name": "test", "version": "1.0", "steps": []}

        assert not self.parser.validate_definition(definition)
        assert "Workflow must have at least one step" in self.parser.validation_errors

    def test_validate_definition_invalid_step(self):
        """Test validation with invalid step."""
        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [
                {"service": "default"}  # Missing name
            ],
        }

        assert not self.parser.validate_definition(definition)
        assert "Step 0 missing required field: name" in self.parser.validation_errors

    def test_validate_definition_unsupported_service(self):
        """Test validation with unsupported service."""
        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [{"name": "step1", "service": "unsupported_service"}],
        }

        assert not self.parser.validate_definition(definition)
        assert (
            "Step 0 unsupported service: unsupported_service"
            in self.parser.validation_errors
        )

    def test_validate_definition_invalid_timeout(self):
        """Test validation with invalid timeout."""
        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [{"name": "step1", "service": "default", "timeout": -1}],
        }

        assert not self.parser.validate_definition(definition)
        assert (
            "Step 0 timeout must be a positive integer" in self.parser.validation_errors
        )

        # Test timeout too large
        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [
                {"name": "step1", "service": "default", "timeout": 7200}  # 2 hours
            ],
        }

        self.parser.validation_errors = []
        assert not self.parser.validate_definition(definition)
        assert any(
            "Step 0 timeout too large" in error
            for error in self.parser.validation_errors
        )

    def test_validate_definition_circular_dependency(self):
        """Test validation with circular dependencies."""
        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [
                {"name": "step1", "service": "default", "depends_on": ["step2"]},
                {"name": "step2", "service": "default", "depends_on": ["step1"]},
            ],
        }

        assert not self.parser.validate_definition(definition)
        assert (
            "Circular dependency detected in workflow steps"
            in self.parser.validation_errors
        )

    def test_validate_definition_unknown_dependency(self):
        """Test validation with unknown dependency."""
        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [
                {"name": "step1", "service": "default", "depends_on": ["unknown_step"]}
            ],
        }

        assert not self.parser.validate_definition(definition)
        assert (
            "Step 'step1' depends on unknown step 'unknown_step'"
            in self.parser.validation_errors
        )

    def test_get_execution_order_linear(self):
        """Test getting execution order for linear workflow."""
        steps = [
            WorkflowStep("step1", "default"),
            WorkflowStep("step2", "default", depends_on=["step1"]),
            WorkflowStep("step3", "default", depends_on=["step2"]),
        ]

        levels = self.parser.get_execution_order(steps)

        assert len(levels) == 3
        assert levels[0] == ["step1"]
        assert levels[1] == ["step2"]
        assert levels[2] == ["step3"]

    def test_get_execution_order_parallel(self):
        """Test getting execution order for parallel workflow."""
        steps = [
            WorkflowStep("step1", "default"),
            WorkflowStep("step2", "default"),
            WorkflowStep("step3", "default", depends_on=["step1", "step2"]),
        ]

        levels = self.parser.get_execution_order(steps)

        assert len(levels) == 2
        assert set(levels[0]) == {"step1", "step2"}
        assert levels[1] == ["step3"]

    def test_get_execution_order_complex(self):
        """Test getting execution order for complex workflow."""
        steps = [
            WorkflowStep("init", "default"),
            WorkflowStep("setup1", "default", depends_on=["init"]),
            WorkflowStep("setup2", "default", depends_on=["init"]),
            WorkflowStep("process", "default", depends_on=["setup1", "setup2"]),
            WorkflowStep("cleanup", "default", depends_on=["process"]),
        ]

        levels = self.parser.get_execution_order(steps)

        assert len(levels) == 4
        assert levels[0] == ["init"]
        assert set(levels[1]) == {"setup1", "setup2"}
        assert levels[2] == ["process"]
        assert levels[3] == ["cleanup"]

    def test_export_to_yaml(self):
        """Test exporting workflow definition to YAML."""
        steps = [
            WorkflowStep("step1", "default", timeout=300, retry=2),
            WorkflowStep("step2", "customer_init_service", depends_on=["step1"]),
        ]

        definition = ParsedWorkflowDefinition(
            name="test_workflow",
            version="1.0",
            description="Test workflow",
            steps=steps,
            global_config={"timeout": 600},
        )

        yaml_output = self.parser.export_to_yaml(definition)

        # Parse the YAML back to verify structure
        parsed_yaml = yaml.safe_load(yaml_output)

        assert parsed_yaml["name"] == "test_workflow"
        assert parsed_yaml["version"] == "1.0"
        assert parsed_yaml["description"] == "Test workflow"
        assert parsed_yaml["config"] == {"timeout": 600}
        assert len(parsed_yaml["steps"]) == 2
        assert parsed_yaml["steps"][0]["name"] == "step1"
        assert parsed_yaml["steps"][1]["depends_on"] == ["step1"]

    def test_validate_definition_max_steps_limit(self):
        """Test validation with too many steps."""
        # Create workflow with too many steps
        steps = [
            {"name": f"step{i}", "service": "default"}
            for i in range(self.parser.MAX_STEPS + 1)
        ]

        definition = {"name": "test", "version": "1.0", "steps": steps}

        assert not self.parser.validate_definition(definition)
        assert (
            f"Too many steps (max {self.parser.MAX_STEPS})"
            in self.parser.validation_errors
        )

    def test_validate_definition_step_name_too_long(self):
        """Test validation with step name too long."""
        long_name = "a" * (self.parser.MAX_STEP_NAME_LENGTH + 1)

        definition = {
            "name": "test",
            "version": "1.0",
            "steps": [{"name": long_name, "service": "default"}],
        }

        assert not self.parser.validate_definition(definition)
        assert (
            f"Step 0 name too long (max {self.parser.MAX_STEP_NAME_LENGTH} chars)"
            in self.parser.validation_errors
        )

    def test_validate_definition_valid_complete(self):
        """Test validation of a complete valid definition."""
        definition = {
            "name": "complete_workflow",
            "version": "2.0",
            "description": "A complete workflow for testing",
            "config": {"global_timeout": 3600, "notification_enabled": True},
            "steps": [
                {
                    "name": "initialize",
                    "service": "customer_init_service",
                    "timeout": 300,
                    "retry": 2,
                    "config": {"setup_folders": True},
                },
                {
                    "name": "process_data",
                    "service": "analysis_engine",
                    "depends_on": ["initialize"],
                    "timeout": 1800,
                    "retry": 1,
                    "config": {"analyzers": ["keyword_match", "search_terms"]},
                },
                {
                    "name": "generate_report",
                    "service": "report_generator",
                    "depends_on": ["process_data"],
                    "timeout": 600,
                    "config": {"formats": ["html", "pdf"]},
                },
            ],
        }

        assert self.parser.validate_definition(definition)
        assert len(self.parser.validation_errors) == 0

        # Test parsing the definition
        parsed = self.parser.parse_definition(definition)
        assert parsed.name == "complete_workflow"
        assert parsed.version == "2.0"
        assert len(parsed.steps) == 3
        assert parsed.global_config["global_timeout"] == 3600
