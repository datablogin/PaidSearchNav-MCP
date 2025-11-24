"""Integration tests for Skills with MCP Server.

These tests verify that skills can successfully interact with the MCP server
and that the required tools are available.
"""

import json
from pathlib import Path

import pytest


class TestSkillMCPIntegration:
    """Test skill integration with MCP server."""

    def test_skill_required_tools_match_mcp_server(self):
        """Verify that skill's required tools exist in MCP server."""
        # Load skill metadata
        skill_json_path = Path("skills/keyword_match_analyzer/skill.json")
        with open(skill_json_path) as f:
            skill_metadata = json.load(f)

        required_tools = skill_metadata["requires_mcp_tools"]

        # Check MCP server.py for tool definitions
        server_path = Path("src/paidsearchnav_mcp/server.py")
        with open(server_path) as f:
            server_content = f.read()

        # Verify each required tool exists
        for tool_name in required_tools:
            # Look for @mcp.tool() decorator followed by function definition
            assert (
                f"async def {tool_name}(" in server_content
            ), f"MCP tool '{tool_name}' not found in server.py"

    def test_get_keywords_tool_exists(self):
        """Verify get_keywords tool exists in MCP server."""
        from paidsearchnav_mcp import server

        # Check if get_keywords function exists
        assert hasattr(server, "get_keywords"), "get_keywords tool not found"

    def test_get_search_terms_tool_exists(self):
        """Verify get_search_terms tool exists in MCP server."""
        from paidsearchnav_mcp import server

        # Check if get_search_terms function exists
        assert hasattr(server, "get_search_terms"), "get_search_terms tool not found"

    def test_skill_packaging_creates_valid_zip(self):
        """Test that skill can be packaged into a valid .zip file."""
        import zipfile

        zip_path = Path("dist/KeywordMatchAnalyzer_v1.0.0.zip")

        # Check zip exists (should have been created by packaging script)
        assert zip_path.exists(), f"Skill package not found: {zip_path}"

        # Verify zip is valid
        assert zipfile.is_zipfile(zip_path), f"Invalid zip file: {zip_path}"

        # Check zip contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_list = zf.namelist()

            # Required files should be in the zip
            expected_files = [
                "keyword_match_analyzer/skill.json",
                "keyword_match_analyzer/prompt.md",
                "keyword_match_analyzer/examples.md",
                "keyword_match_analyzer/README.md",
            ]

            for expected_file in expected_files:
                assert expected_file in file_list, f"Missing file in package: {expected_file}"

            # Validate skill.json is valid JSON
            skill_json_content = zf.read("keyword_match_analyzer/skill.json")
            skill_metadata = json.loads(skill_json_content)

            assert skill_metadata["name"] == "KeywordMatchAnalyzer"
            assert skill_metadata["version"] == "1.0.0"


class TestMCPToolResponses:
    """Test that MCP tools return data in expected format for skills."""

    @pytest.mark.skip(reason="Requires live MCP server and credentials - manual testing only")
    @pytest.mark.asyncio
    async def test_get_keywords_response_format(self):
        """Verify get_keywords returns data in format expected by skill.

        NOTE: This test is skipped in automated runs. It requires:
        - MCP server running
        - Valid Google Ads credentials
        - Customer ID with data

        To run manually: pytest tests/integration/test_skill_with_mcp.py::TestMCPToolResponses::test_get_keywords_response_format -v -s
        """
        from paidsearchnav_mcp.server import KeywordsRequest, get_keywords

        # Create request
        request = KeywordsRequest(
            customer_id="1234567890",
            start_date="2025-08-01",
            end_date="2025-11-22",
        )

        response = await get_keywords(request)

        # Check response structure
        assert "status" in response
        assert response["status"] in ["success", "error"]

        if response["status"] == "success":
            assert "data" in response
            assert isinstance(response["data"], list)

            # Check that data items have required fields for skill
            if len(response["data"]) > 0:
                keyword = response["data"][0]
                required_fields = [
                    "keyword",
                    "match_type",
                    "impressions",
                    "clicks",
                    "cost_micros",
                    "conversions",
                ]

                for field in required_fields:
                    assert field in keyword, f"Missing required field: {field}"

    @pytest.mark.skip(reason="Requires live MCP server and credentials - manual testing only")
    @pytest.mark.asyncio
    async def test_get_search_terms_response_format(self):
        """Verify get_search_terms returns data in format expected by skill.

        NOTE: This test is skipped in automated runs. It requires:
        - MCP server running
        - Valid Google Ads credentials
        - Customer ID with data

        To run manually: pytest tests/integration/test_skill_with_mcp.py::TestMCPToolResponses::test_get_search_terms_response_format -v -s
        """
        from paidsearchnav_mcp.server import SearchTermsRequest, get_search_terms

        # Create request
        request = SearchTermsRequest(
            customer_id="1234567890",
            start_date="2025-08-01",
            end_date="2025-11-22",
        )

        response = await get_search_terms(request)

        # Check response structure
        assert "status" in response
        assert response["status"] in ["success", "error"]

        if response["status"] == "success":
            assert "data" in response
            assert isinstance(response["data"], list)

            # Check that data items have required fields for skill
            if len(response["data"]) > 0:
                search_term = response["data"][0]
                required_fields = [
                    "search_term",
                    "keyword",
                    "impressions",
                    "clicks",
                    "cost_micros",
                ]

                for field in required_fields:
                    assert field in search_term, f"Missing required field: {field}"


class TestSkillDocumentation:
    """Test that skill documentation is complete and accurate."""

    def test_skill_readme_has_required_sections(self):
        """Verify README has all required documentation sections."""
        readme_path = Path("skills/keyword_match_analyzer/README.md")
        with open(readme_path) as f:
            content = f.read()

        required_sections = [
            "Business Value",
            "Use Cases",
            "Required MCP Tools",
            "How It Works",
            "Usage",
            "Configuration",
            "Output Structure",
            "Best Practices",
            "Troubleshooting",
        ]

        for section in required_sections:
            assert section in content, f"README missing required section: {section}"

    def test_skill_examples_are_complete(self):
        """Verify examples.md has complete input/output pairs."""
        examples_path = Path("skills/keyword_match_analyzer/examples.md")
        with open(examples_path) as f:
            content = f.read()

        # Check for example structure markers
        assert "Input Data" in content
        assert "Expected Output" in content or "Expected Analysis Output" in content

        # Should have multiple examples
        assert content.count("## Example") >= 3

    def test_development_guide_exists(self):
        """Verify skill development guide was created."""
        guide_path = Path("docs/SKILL_DEVELOPMENT_GUIDE.md")
        assert guide_path.exists()

        with open(guide_path) as f:
            content = f.read()

        required_topics = [
            "Skill Anatomy",
            "Conversion Process",
            "Testing Strategy",
            "Best Practices",
            "Distribution",
        ]

        for topic in required_topics:
            assert topic in content, f"Development guide missing topic: {topic}"

    def test_analyzer_pattern_documentation_exists(self):
        """Verify analyzer pattern documentation was created."""
        pattern_doc = Path("docs/analyzer_patterns/keyword_match_logic.md")
        assert pattern_doc.exists()

        with open(pattern_doc) as f:
            content = f.read()

        required_sections = [
            "Business Logic",
            "Analysis Methodology",
            "Configuration Parameters",
            "Recommendation Generation",
        ]

        for section in required_sections:
            assert section in content, f"Pattern doc missing section: {section}"
