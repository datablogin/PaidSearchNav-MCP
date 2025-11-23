"""Tests for script template management."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from paidsearchnav_mcp.platforms.google.scripts.base import ScriptType
from paidsearchnav_mcp.platforms.google.scripts.templates import (
    ScriptTemplate,
    TemplateManager,
)


class TestScriptTemplate:
    """Test ScriptTemplate functionality."""

    def test_template_initialization(self):
        """Test template initialization."""
        template = ScriptTemplate(
            id="test_template",
            name="Test Template",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test description",
            version="1.0.0",
            code_template="function main() { var test = {value}; }",
            parameters=[
                {
                    "name": "value",
                    "type": "string",
                    "description": "Test value",
                    "required": True,
                }
            ],
            tags=["test", "example"],
        )

        assert template.id == "test_template"
        assert template.name == "Test Template"
        assert template.type == ScriptType.NEGATIVE_KEYWORD
        assert template.version == "1.0.0"
        assert len(template.parameters) == 1
        assert template.tags == ["test", "example"]

    def test_render_template_success(self):
        """Test successful template rendering."""
        template = ScriptTemplate(
            id="test",
            name="Test",
            type=ScriptType.CONFLICT_DETECTION,
            description="Test",
            version="1.0.0",
            code_template="var cost = << cost_threshold >>; var days = << lookback_days >>;",
        )

        result = template.render(
            {
                "cost_threshold": 50.0,
                "lookback_days": 30,
            }
        )

        assert result == "var cost = 50.0; var days = 30;"

    def test_render_template_missing_parameter(self):
        """Test template rendering with missing parameter."""
        template = ScriptTemplate(
            id="test",
            name="Test",
            type=ScriptType.PLACEMENT_AUDIT,
            description="Test",
            version="1.0.0",
            code_template="var value = << missing_param >>;",
        )

        with pytest.raises(ValueError, match="Failed to render template"):
            template.render({})

    def test_validate_params_success(self):
        """Test successful parameter validation."""
        template = ScriptTemplate(
            id="test",
            name="Test",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            version="1.0.0",
            code_template="",
            parameters=[
                {"name": "param1", "type": "string", "required": True},
                {"name": "param2", "type": "number", "required": False},
            ],
        )

        errors = template.validate_params(
            {
                "param1": "value",
                "param2": 42,
            }
        )

        assert errors == []

    def test_validate_params_missing_required(self):
        """Test parameter validation with missing required param."""
        template = ScriptTemplate(
            id="test",
            name="Test",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            version="1.0.0",
            code_template="",
            parameters=[
                {"name": "required_param", "type": "string", "required": True},
            ],
        )

        errors = template.validate_params({})

        assert len(errors) == 1
        assert "Missing required parameter: required_param" in errors[0]

    def test_validate_params_type_validation(self):
        """Test parameter type validation."""
        template = ScriptTemplate(
            id="test",
            name="Test",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            version="1.0.0",
            code_template="",
            parameters=[
                {"name": "string_param", "type": "string", "required": True},
                {"name": "number_param", "type": "number", "required": True},
                {"name": "boolean_param", "type": "boolean", "required": True},
                {"name": "array_param", "type": "array", "required": True},
                {"name": "object_param", "type": "object", "required": True},
            ],
        )

        # Test with correct types
        errors = template.validate_params(
            {
                "string_param": "test",
                "number_param": 42,
                "boolean_param": True,
                "array_param": [1, 2, 3],
                "object_param": {"key": "value"},
            }
        )
        assert errors == []

        # Test with incorrect types
        errors = template.validate_params(
            {
                "string_param": 123,  # Should be string
                "number_param": "not a number",  # Should be number
                "boolean_param": "yes",  # Should be boolean
                "array_param": "not an array",  # Should be array
                "object_param": [1, 2, 3],  # Should be object
            }
        )

        assert len(errors) == 5
        assert any("string_param" in e for e in errors)
        assert any("number_param" in e for e in errors)
        assert any("boolean_param" in e for e in errors)
        assert any("array_param" in e for e in errors)
        assert any("object_param" in e for e in errors)


class TestTemplateManager:
    """Test TemplateManager functionality."""

    def test_manager_initialization(self):
        """Test template manager initialization."""
        manager = TemplateManager()

        # Should have built-in templates loaded
        templates = manager.list_templates()
        assert len(templates) > 0

        # Check for specific built-in templates
        neg_keyword_template = manager.get_template("negative_keyword_performance")
        assert neg_keyword_template is not None
        assert neg_keyword_template.type == ScriptType.NEGATIVE_KEYWORD

        conflict_template = manager.get_template("conflict_detection")
        assert conflict_template is not None
        assert conflict_template.type == ScriptType.CONFLICT_DETECTION

        placement_template = manager.get_template("placement_audit")
        assert placement_template is not None
        assert placement_template.type == ScriptType.PLACEMENT_AUDIT

    def test_get_template(self):
        """Test getting a template by ID."""
        manager = TemplateManager()

        template = manager.get_template("negative_keyword_performance")
        assert template is not None
        assert template.id == "negative_keyword_performance"

        # Test non-existent template
        template = manager.get_template("non_existent")
        assert template is None

    def test_list_templates(self):
        """Test listing templates."""
        manager = TemplateManager()

        # List all templates
        all_templates = manager.list_templates()
        assert len(all_templates) >= 3  # At least the built-in ones

        # List by type
        neg_templates = manager.list_templates(ScriptType.NEGATIVE_KEYWORD)
        assert all(t.type == ScriptType.NEGATIVE_KEYWORD for t in neg_templates)

        conflict_templates = manager.list_templates(ScriptType.CONFLICT_DETECTION)
        assert all(t.type == ScriptType.CONFLICT_DETECTION for t in conflict_templates)

    def test_register_template(self):
        """Test registering a custom template."""
        manager = TemplateManager()

        custom_template = ScriptTemplate(
            id="custom_test",
            name="Custom Test",
            type=ScriptType.N_GRAM_ANALYSIS,
            description="Custom template",
            version="1.0.0",
            code_template="// Custom code",
        )

        manager.register_template(custom_template)

        # Should be able to retrieve it
        retrieved = manager.get_template("custom_test")
        assert retrieved is not None
        assert retrieved.id == "custom_test"
        assert retrieved.type == ScriptType.N_GRAM_ANALYSIS

    def test_load_from_file(self):
        """Test loading template from file."""
        manager = TemplateManager()

        # Create a temporary template file
        template_data = {
            "id": "file_template",
            "name": "File Template",
            "type": "master_negative_list",
            "description": "Template from file",
            "version": "1.0.0",
            "code_template": "// Code from file",
            "parameters": [{"name": "param1", "type": "string", "required": True}],
            "tags": ["file", "test"],
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(template_data, f)
            temp_path = Path(f.name)

        try:
            # Load the template
            template = manager.load_from_file(temp_path)

            assert template.id == "file_template"
            assert template.name == "File Template"
            assert template.type == ScriptType.MASTER_NEGATIVE_LIST
            assert len(template.parameters) == 1
            assert template.tags == ["file", "test"]

            # Should be registered
            retrieved = manager.get_template("file_template")
            assert retrieved is not None

        finally:
            temp_path.unlink()

    def test_save_to_file(self):
        """Test saving template to file."""
        manager = TemplateManager()

        template = ScriptTemplate(
            id="save_test",
            name="Save Test",
            type=ScriptType.PLACEMENT_AUDIT,
            description="Template to save",
            version="2.0.0",
            code_template="// Save test code",
            parameters=[{"name": "test_param", "type": "number", "required": False}],
            tags=["save", "test"],
        )

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Save the template
            manager.save_to_file(template, temp_path)

            # Load it back and verify
            with open(temp_path, "r") as f:
                data = json.load(f)

            assert data["id"] == "save_test"
            assert data["name"] == "Save Test"
            assert data["type"] == "placement_audit"
            assert data["version"] == "2.0.0"
            assert len(data["parameters"]) == 1
            assert data["tags"] == ["save", "test"]

        finally:
            temp_path.unlink()

    def test_builtin_template_rendering(self):
        """Test rendering of built-in templates."""
        manager = TemplateManager()

        # Test negative keyword performance template
        neg_template = manager.get_template("negative_keyword_performance")
        rendered = neg_template.render(
            {
                "cost_threshold": 100,
                "conversion_threshold": 0,
                "lookback_days": 30,
            }
        )

        assert "var costThreshold = 100;" in rendered
        assert "var conversionThreshold = 0;" in rendered
        assert "var lookbackDays = 30;" in rendered
        assert "function main()" in rendered

        # Test conflict detection template
        conflict_template = manager.get_template("conflict_detection")
        rendered = conflict_template.render(
            {
                "check_campaign_level": True,
                "check_adgroup_level": True,
            }
        )

        assert "var checkCampaignLevel = True;" in rendered
        assert "var checkAdGroupLevel = True;" in rendered
        assert "function isConflict" in rendered

        # Test placement audit template
        placement_template = manager.get_template("placement_audit")
        rendered = placement_template.render(
            {
                "min_impressions": 200,
                "max_cpa_ratio": 3.0,
            }
        )

        assert "var minImpressions = 200;" in rendered
        assert "var maxCpaRatio = 3.0;" in rendered
        assert "AUTOMATIC_PLACEMENTS_PERFORMANCE_REPORT" in rendered
