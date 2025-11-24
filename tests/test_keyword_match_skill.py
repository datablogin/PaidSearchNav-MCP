"""Tests for Keyword Match Analyzer Skill.

These tests validate the skill's ability to correctly identify match type
optimization opportunities and generate appropriate recommendations.
"""


import pytest

# Sample test data based on archived analyzer test data
SAMPLE_KEYWORDS = [
    {
        "keyword": "running shoes",
        "match_type": "BROAD",
        "impressions": 10000,
        "clicks": 450,
        "cost_micros": 22500000,  # $22.50
        "conversions": 45,
        "conversion_value_micros": 45000000,  # $45
        "quality_score": 8,
    },
    {
        "keyword": "trail running shoes",
        "match_type": "PHRASE",
        "impressions": 2500,
        "clicks": 180,
        "cost_micros": 7200000,  # $7.20
        "conversions": 22,
        "conversion_value_micros": 26400000,  # $26.40
        "quality_score": 9,
    },
    {
        "keyword": "shoes",
        "match_type": "BROAD",
        "impressions": 50000,
        "clicks": 1200,
        "cost_micros": 60000000,  # $60
        "conversions": 10,
        "conversion_value_micros": 10000000,  # $10
        "quality_score": 4,
    },
]

SAMPLE_SEARCH_TERMS = [
    {
        "search_term": "running shoes",
        "keyword": "running shoes",
        "impressions": 7500,
        "clicks": 380,
        "cost_micros": 19000000,  # $19
        "conversions": 40,
    },
    {
        "search_term": "best running shoes",
        "keyword": "running shoes",
        "impressions": 1500,
        "clicks": 45,
        "cost_micros": 2250000,  # $2.25
        "conversions": 3,
    },
    {
        "search_term": "cheap running shoes",
        "keyword": "running shoes",
        "impressions": 1000,
        "clicks": 25,
        "cost_micros": 1250000,  # $1.25
        "conversions": 2,
    },
]


class TestKeywordMatchSkillLogic:
    """Test core business logic of the skill."""

    def test_calculate_match_type_stats(self):
        """Test match type statistics calculation."""
        # Group by match type
        stats = {}
        for kw in SAMPLE_KEYWORDS:
            match_type = kw["match_type"]
            if match_type not in stats:
                stats[match_type] = {
                    "count": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "cost": 0,
                    "conversions": 0,
                }

            stats[match_type]["count"] += 1
            stats[match_type]["impressions"] += kw["impressions"]
            stats[match_type]["clicks"] += kw["clicks"]
            stats[match_type]["cost"] += kw["cost_micros"] / 1_000_000
            stats[match_type]["conversions"] += kw["conversions"]

        # Verify BROAD stats
        assert stats["BROAD"]["count"] == 2
        assert stats["BROAD"]["clicks"] == 1650  # 450 + 1200
        assert stats["BROAD"]["cost"] == 82.50  # $22.50 + $60
        assert stats["BROAD"]["conversions"] == 55  # 45 + 10

        # Verify PHRASE stats
        assert stats["PHRASE"]["count"] == 1
        assert stats["PHRASE"]["clicks"] == 180
        assert stats["PHRASE"]["cost"] == 7.20

    def test_identify_high_cost_broad_keywords(self):
        """Test identification of high-cost broad match keywords."""
        high_cost_broad = []

        for kw in SAMPLE_KEYWORDS:
            if kw["match_type"] != "BROAD":
                continue

            cost = kw["cost_micros"] / 1_000_000
            if cost < 100:  # Below high_cost_threshold
                continue

            # Calculate ROAS
            conversions = kw["conversions"]
            conversion_value = kw["conversion_value_micros"] / 1_000_000
            roas = conversion_value / cost if cost > 0 else 0

            # Check for low ROI
            if roas < 1.5 or (conversions > 0 and cost / conversions > 0):
                high_cost_broad.append(kw)

        # Should not find any (both BROAD keywords cost < $100)
        assert len(high_cost_broad) == 0

    def test_identify_low_quality_keywords(self):
        """Test identification of low quality score keywords."""
        low_quality = [
            kw for kw in SAMPLE_KEYWORDS if kw["quality_score"] < 7 and kw["cost_micros"] > 0
        ]

        # Should find "shoes" keyword (QS=4)
        assert len(low_quality) == 1
        assert low_quality[0]["keyword"] == "shoes"
        assert low_quality[0]["quality_score"] == 4

    def test_search_term_concentration(self):
        """Test calculation of search term concentration."""
        # For "running shoes" keyword
        keyword_impressions = SAMPLE_KEYWORDS[0]["impressions"]  # 10000
        primary_search_term_impressions = SAMPLE_SEARCH_TERMS[0]["impressions"]  # 7500

        concentration = primary_search_term_impressions / keyword_impressions
        assert concentration == 0.75  # 75%

        # This should trigger exact match recommendation (≥70% threshold)
        assert concentration >= 0.70

    def test_minimum_click_threshold(self):
        """Test that keywords below click threshold are filtered."""
        min_clicks = 100

        # Test with keyword that has enough clicks
        kw1 = {"keyword": "test1", "clicks": 150, "match_type": "BROAD"}
        is_candidate_1 = kw1["clicks"] >= min_clicks
        assert is_candidate_1 is True

        # Test with keyword below threshold
        kw2 = {"keyword": "test2", "clicks": 50, "match_type": "BROAD"}
        is_candidate_2 = kw2["clicks"] >= min_clicks
        assert is_candidate_2 is False

    def test_duplicate_keyword_detection(self):
        """Test detection of duplicate keywords across match types."""
        # Create test data with duplicates
        duplicate_keywords = [
            {"keyword": "running shoes", "match_type": "BROAD", "cost_micros": 22500000, "conversions": 45},
            {"keyword": "running shoes", "match_type": "PHRASE", "cost_micros": 11200000, "conversions": 35},
            {"keyword": "running shoes", "match_type": "EXACT", "cost_micros": 6000000, "conversions": 20},
        ]

        # Group by normalized text
        text_groups = {}
        for kw in duplicate_keywords:
            text = kw["keyword"].lower().strip()
            if text not in text_groups:
                text_groups[text] = []
            text_groups[text].append(kw)

        # Should find one group with 3 keywords
        assert len(text_groups) == 1
        assert "running shoes" in text_groups
        assert len(text_groups["running shoes"]) == 3

        # Calculate performance by match type
        match_type_perf = {}
        for kw in text_groups["running shoes"]:
            mt = kw["match_type"]
            cost = kw["cost_micros"] / 1_000_000
            conversions = kw["conversions"]
            cpa = cost / conversions if conversions > 0 else float("inf")

            match_type_perf[mt] = {"cpa": cpa}

        # EXACT should have best CPA
        assert match_type_perf["EXACT"]["cpa"] < match_type_perf["PHRASE"]["cpa"]
        assert match_type_perf["PHRASE"]["cpa"] < match_type_perf["BROAD"]["cpa"]

    def test_potential_savings_calculation(self):
        """Test conservative savings calculation."""
        # Test case: keyword with zero conversions and high spend
        kw = {
            "keyword": "expensive keyword",
            "match_type": "BROAD",
            "cost_micros": 150000000,  # $150
            "conversions": 0,
        }

        cost = kw["cost_micros"] / 1_000_000
        conversions = kw["conversions"]

        if conversions == 0:
            # Assume 80% savings for zero-conversion keywords
            savings = cost * 0.8
        else:
            savings = 0

        assert savings == 120.0  # $150 * 0.8

    def test_cpa_comparison(self):
        """Test CPA comparison logic."""
        # Calculate CPAs for each keyword
        cpas = []
        for kw in SAMPLE_KEYWORDS:
            cost = kw["cost_micros"] / 1_000_000
            conversions = kw["conversions"]
            cpa = cost / conversions if conversions > 0 else 0
            cpas.append({"keyword": kw["keyword"], "cpa": cpa})

        # "shoes" should have highest CPA
        shoes_cpa = next(c["cpa"] for c in cpas if c["keyword"] == "shoes")
        running_shoes_cpa = next(c["cpa"] for c in cpas if c["keyword"] == "running shoes")
        trail_shoes_cpa = next(c["cpa"] for c in cpas if c["keyword"] == "trail running shoes")

        assert shoes_cpa > running_shoes_cpa  # $6.00 > $0.50
        assert shoes_cpa > trail_shoes_cpa  # $6.00 > $0.33


class TestKeywordMatchSkillIntegration:
    """Test skill integration with MCP tools."""

    @pytest.mark.asyncio
    async def test_skill_requires_correct_mcp_tools(self):
        """Test that skill metadata specifies correct required tools."""
        import json
        from pathlib import Path

        skill_json_path = Path("skills/keyword_match_analyzer/skill.json")
        assert skill_json_path.exists()

        with open(skill_json_path) as f:
            metadata = json.load(f)

        # Verify required tools are specified
        assert "requires_mcp_tools" in metadata
        required_tools = metadata["requires_mcp_tools"]

        assert "get_keywords" in required_tools
        assert "get_search_terms" in required_tools

    def test_skill_files_exist(self):
        """Test that all required skill files exist."""
        from pathlib import Path

        skill_dir = Path("skills/keyword_match_analyzer")
        assert skill_dir.exists()

        required_files = ["skill.json", "prompt.md", "examples.md", "README.md"]

        for filename in required_files:
            file_path = skill_dir / filename
            assert file_path.exists(), f"Missing required file: {filename}"

    def test_skill_prompt_structure(self):
        """Test that prompt.md has required sections."""
        from pathlib import Path

        prompt_path = Path("skills/keyword_match_analyzer/prompt.md")
        with open(prompt_path) as f:
            content = f.read()

        # Check for required sections
        required_sections = [
            "Analysis Methodology",
            "Retrieve Data",
            "Calculate Match Type Performance",
            "Identify High-Cost Broad Match Keywords",
            "Output Format",
            "Recommendations",
        ]

        for section in required_sections:
            assert section in content, f"Missing required section: {section}"

    def test_skill_examples_structure(self):
        """Test that examples.md has diverse scenarios."""
        from pathlib import Path

        examples_path = Path("skills/keyword_match_analyzer/examples.md")
        with open(examples_path) as f:
            content = f.read()

        # Check for diverse example scenarios
        expected_scenarios = [
            "Clear Exact Match Opportunity",
            "Do NOT Recommend",
            "Insufficient Data",
            "Multiple Issues",
            "Duplicate Keywords",
        ]

        found_scenarios = sum(1 for scenario in expected_scenarios if scenario in content)
        assert found_scenarios >= 3, "Should have at least 3 different example scenarios"


class TestKeywordMatchSkillValidation:
    """Test validation and edge cases."""

    def test_minimum_impressions_filter(self):
        """Test that keywords below minimum impressions are filtered."""
        min_impressions = 100

        test_keywords = [
            {"keyword": "high volume", "impressions": 5000},
            {"keyword": "medium volume", "impressions": 150},
            {"keyword": "low volume", "impressions": 50},
        ]

        filtered = [kw for kw in test_keywords if kw["impressions"] >= min_impressions]

        assert len(filtered) == 2
        assert all(kw["impressions"] >= min_impressions for kw in filtered)

    def test_roas_calculation(self):
        """Test ROAS calculation accuracy."""
        # Test case 1: Profitable keyword
        kw1 = {"cost_micros": 1000000, "conversion_value_micros": 2500000}  # $1  # $2.50
        cost1 = kw1["cost_micros"] / 1_000_000
        value1 = kw1["conversion_value_micros"] / 1_000_000
        roas1 = value1 / cost1 if cost1 > 0 else 0
        assert roas1 == 2.5

        # Test case 2: Unprofitable keyword
        kw2 = {"cost_micros": 1000000, "conversion_value_micros": 500000}  # $1  # $0.50
        cost2 = kw2["cost_micros"] / 1_000_000
        value2 = kw2["conversion_value_micros"] / 1_000_000
        roas2 = value2 / cost2 if cost2 > 0 else 0
        assert roas2 == 0.5

    def test_quality_score_threshold(self):
        """Test quality score threshold logic."""
        low_qs_threshold = 7

        keywords = [
            {"keyword": "excellent", "quality_score": 10},
            {"keyword": "good", "quality_score": 8},
            {"keyword": "borderline", "quality_score": 7},
            {"keyword": "poor", "quality_score": 5},
            {"keyword": "very poor", "quality_score": 3},
        ]

        low_qs_keywords = [kw for kw in keywords if kw["quality_score"] < low_qs_threshold]

        assert len(low_qs_keywords) == 2  # "poor" and "very poor"
        assert all(kw["quality_score"] < low_qs_threshold for kw in low_qs_keywords)

    def test_broad_match_cpa_multiplier(self):
        """Test broad match CPA multiplier threshold."""
        max_multiplier = 2.0

        # Account average CPA
        total_cost = sum(kw["cost_micros"] / 1_000_000 for kw in SAMPLE_KEYWORDS)
        total_conversions = sum(kw["conversions"] for kw in SAMPLE_KEYWORDS)
        avg_cpa = total_cost / total_conversions if total_conversions > 0 else 0

        # Broad match CPA
        broad_keywords = [kw for kw in SAMPLE_KEYWORDS if kw["match_type"] == "BROAD"]
        broad_cost = sum(kw["cost_micros"] / 1_000_000 for kw in broad_keywords)
        broad_conversions = sum(kw["conversions"] for kw in broad_keywords)
        broad_cpa = broad_cost / broad_conversions if broad_conversions > 0 else 0

        # Check if broad exceeds threshold
        if broad_cpa > avg_cpa * max_multiplier:
            should_flag = True
        else:
            should_flag = False

        # With our sample data, broad CPA is ~$1.50, avg is ~$1.15
        # So 1.50 / 1.15 = 1.3, which is < 2.0
        assert should_flag is False


class TestSkillPackaging:
    """Test skill packaging for distribution."""

    def test_skill_json_valid_structure(self):
        """Test that skill.json has all required fields."""
        import json
        from pathlib import Path

        skill_json_path = Path("skills/keyword_match_analyzer/skill.json")
        with open(skill_json_path) as f:
            metadata = json.load(f)

        required_fields = [
            "name",
            "version",
            "description",
            "author",
            "category",
            "requires_mcp_tools",
            "output_format",
            "use_cases",
            "business_value",
        ]

        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"

        # Validate types
        assert isinstance(metadata["name"], str)
        assert isinstance(metadata["version"], str)
        assert isinstance(metadata["requires_mcp_tools"], list)
        assert isinstance(metadata["use_cases"], list)

    def test_skill_version_format(self):
        """Test that version follows semantic versioning."""
        import json
        import re
        from pathlib import Path

        skill_json_path = Path("skills/keyword_match_analyzer/skill.json")
        with open(skill_json_path) as f:
            metadata = json.load(f)

        version = metadata["version"]
        # Check semver format: X.Y.Z
        assert re.match(r"^\d+\.\d+\.\d+$", version), f"Invalid version format: {version}"
