# PaidSearchNav Skill Development Guide

This guide explains how to convert PaidSearchNav analyzers into Claude Skills that work with the MCP server.

## Overview

**Skills** are the new architecture for analysis logic in PaidSearchNav. Instead of monolithic Python classes, each analyzer becomes a Claude Skill that:

1. Uses natural language prompts to define analysis methodology
2. Calls MCP tools to fetch data from Google Ads API and BigQuery
3. Generates markdown reports with prioritized recommendations
4. Can be distributed as standalone .zip packages

## Why Skills?

### Before (Monolithic Architecture)
```python
class KeywordMatchAnalyzer(Analyzer):
    def __init__(self, data_provider, thresholds...):
        # 400+ lines of Python code
        # Tightly coupled to data layer
        # Hard to test without full environment
        # Slow iteration (requires Docker rebuild)
```

### After (Claude Skills)
```markdown
# keyword_match_analyzer/prompt.md
You are a keyword match type optimization specialist.

## Analysis Methodology
1. Use `get_keywords` MCP tool to fetch data
2. Calculate match type performance
3. Generate recommendations

[Rest of analysis logic in natural language]
```

### Advantages

1. **Faster Iteration**: Change analysis logic by editing markdown, not rebuilding Docker
2. **Better Transparency**: Analysis methodology is human-readable
3. **Easier Testing**: Test with mock MCP responses, no database needed
4. **Independent Deployment**: Skills update independently of MCP server
5. **Claude-Powered**: Leverage Claude's reasoning for complex analysis

## Skill Anatomy

A complete skill consists of 5 core files:

### 1. `skill.json` - Metadata

Defines the skill's identity and requirements:

```json
{
  "name": "KeywordMatchAnalyzer",
  "version": "1.0.0",
  "description": "Analyzes keyword match types...",
  "author": "PaidSearchNav",
  "category": "cost_efficiency",
  "requires_mcp_tools": [
    "get_keywords",
    "get_search_terms"
  ],
  "output_format": "markdown",
  "use_cases": [
    "Quarterly keyword audits",
    "Cost efficiency analysis"
  ],
  "business_value": "Typically saves 15-30% on cost per conversion..."
}
```

**Key Fields**:
- `requires_mcp_tools`: List of MCP tools the skill needs
- `category`: Groups related skills (cost_efficiency, quality, performance, etc.)
- `business_value`: ROI statement for users

### 2. `prompt.md` - Core Analysis Logic

The heart of the skill - detailed instructions for Claude:

```markdown
# Keyword Match Type Analysis Prompt

You are a Google Ads optimization specialist...

## Analysis Methodology

### 1. Retrieve Data
Use MCP tool `get_keywords` to fetch...

### 2. Calculate Performance
For each match type, calculate:
- CPA: `cost / conversions`
- ROAS: `conversion_value / cost`
...

### 3. Generate Recommendations
Create prioritized recommendations:

#### HIGH Priority: [Criteria]
**Trigger**: [When to recommend]
**Action**: [What to do]
...

## Output Format
[Exact markdown structure expected]
```

**Best Practices**:
- **Be specific**: Define exact calculations, thresholds, formulas
- **Show examples**: Include sample analysis patterns
- **Explain "why"**: Provide business context, not just instructions
- **Define edge cases**: Handle insufficient data, zero conversions, etc.
- **Format consistently**: Specify exact table structures, headings, etc.

### 3. `examples.md` - Few-Shot Learning

Concrete input/output pairs that train Claude on expected behavior:

```markdown
## Example 1: Clear Exact Match Opportunity

### Input Data
[JSON from MCP tools]

### Expected Output
[Markdown analysis with recommendations]

### Why This Recommendation
[Explanation of the logic]
```

**Include Examples For**:
- ✅ Positive cases (recommend action)
- ✅ Negative cases (no action needed)
- ✅ Edge cases (insufficient data)
- ✅ Complex scenarios (multiple issues)
- ✅ Well-optimized (no changes needed)

### 4. `README.md` - User Documentation

User-facing guide for the skill:

- **Business Value**: What savings/improvements to expect
- **Use Cases**: When to use this skill
- **How It Works**: High-level methodology
- **Usage Examples**: Natural language prompts that trigger the skill
- **Configuration**: Customizable thresholds and parameters
- **Output Structure**: What the report includes
- **Best Practices**: How to use results effectively
- **Troubleshooting**: Common issues and solutions

### 5. `tests/` - Test Suite

Python tests that validate skill logic:

```python
def test_identify_high_cost_broad_keywords():
    """Test identification logic matches expected behavior."""
    # Test core business logic
    # Validate calculations
    # Check edge cases
```

## Conversion Process

### Step 1: Review Original Analyzer

Read the legacy analyzer code and extract:

```python
# From: archive/old_app/paidsearchnav/analyzers/keyword_match.py

class KeywordMatchAnalyzer(Analyzer):
    def __init__(self, min_impressions=100, ...):
        # Extract these thresholds
        self.min_impressions = min_impressions
        self.high_cost_threshold = high_cost_threshold
        ...
```

**Document**:
- Configuration parameters and defaults
- Core algorithm logic
- Calculation formulas
- Recommendation trigger conditions
- Output format and structure

**Create**: `docs/analyzer_patterns/{analyzer_name}_logic.md`

### Step 2: Design Skill Structure

Map analyzer to skill:

| Analyzer Component | Skill Equivalent |
|--------------------|------------------|
| `__init__` parameters | Configurable thresholds in `prompt.md` |
| Core methods | Sections in Analysis Methodology |
| Calculation logic | Step-by-step formulas in prompt |
| Data fetching | MCP tool calls specified in `requires_mcp_tools` |
| Recommendations | Prioritized recommendation sections |
| Report output | Markdown template in Output Format section |

### Step 3: Write the Prompt

**Template Structure**:

```markdown
# [Analyzer Name] Prompt

You are a [role/specialist]...

## Analysis Methodology

### 1. Retrieve Data
- Use MCP tool `[tool_name]` to fetch [data type]
- Parameters: [required params]
- Filters: [how to filter data]

### 2. [Analysis Step 1]
[Detailed instructions]

**Calculation**: [Formula or algorithm]

**Example**:
```
[Concrete example showing the calculation]
```

### 3. [Analysis Step 2]
...

## Recommendations

### HIGH Priority: [Name]
**Criteria**: [When to recommend]
**Impact**: [Expected savings/improvement]
**Action Steps**:
1. [Specific action]
2. [Specific action]

### MEDIUM Priority: [Name]
...

## Output Format

```markdown
# [Report Title]

[Exact structure expected]
```

## Edge Cases

- **[Case]**: [How to handle]
- **[Case]**: [How to handle]
```

### Step 4: Create Examples

For each major scenario, provide:

1. **Realistic Input Data**: Use actual values from test data
2. **Expected Analysis**: Show the thought process
3. **Correct Output**: Exact markdown that should be generated
4. **Explanation**: Why this recommendation is correct

**Good Example**:
```markdown
## Example 2: Do NOT Recommend (Insufficient Data)

### Input
{"keyword": "test", "clicks": 15, ...}

### Expected Output
**No Recommendation**: Insufficient click volume (15 < 100 required)

### Reasoning
With only 15 clicks, we cannot confidently recommend match type changes.
Sample size is too small to draw statistical conclusions.
```

### Step 5: Write Tests

Test the skill's business logic:

```python
class TestSkillLogic:
    def test_threshold_application(self):
        """Verify threshold logic works correctly."""
        # Arrange
        keyword = {"cost_micros": 150000000}  # $150
        threshold = 100

        # Act
        exceeds_threshold = (keyword["cost_micros"] / 1_000_000) >= threshold

        # Assert
        assert exceeds_threshold is True

    def test_calculation_accuracy(self):
        """Verify calculations match expected formulas."""
        # Test ROAS, CPA, etc.
```

### Step 6: Validate Against Original

Compare skill output to original analyzer:

1. Run original analyzer on test data
2. Use skill with same test data (via Claude)
3. Compare recommendations
4. Ensure no regressions in logic

**Document discrepancies** in `docs/analyzer_patterns/{name}_logic.md`

## Testing Strategy

### Unit Tests (Python)
Test core business logic:
- Threshold detection
- Calculation accuracy
- Data filtering
- Edge case handling

### Integration Tests
Test MCP tool integration:
- Skill specifies correct required tools
- Tool responses are handled properly
- Error states are managed gracefully

### Manual Validation
Test with real data:
- Run skill via Claude with live MCP server
- Compare output to expected format
- Verify recommendations are actionable
- Check savings estimates are reasonable

## Distribution

### Packaging a Skill

Use the packaging script:

```bash
python scripts/package_skill.py keyword_match_analyzer
```

This creates: `dist/KeywordMatchAnalyzer_v1.0.0.zip`

Contents:
```
KeywordMatchAnalyzer_v1.0.0.zip
├── skill.json
├── prompt.md
├── examples.md
└── README.md
```

### Installation (User Side)

1. Download .zip from releases
2. Upload to Claude
3. Connect Claude to MCP server
4. Use skill with natural language

Example:
```
User: "Analyze keywords for customer 1234567890 and identify match type opportunities"

Claude: [Loads KeywordMatchAnalyzer skill]
        [Calls get_keywords MCP tool]
        [Analyzes data per prompt.md methodology]
        [Generates markdown report]
```

## Best Practices

### Prompt Writing

✅ **DO**:
- Be extremely specific about calculations
- Include concrete examples inline
- Explain business context and "why"
- Define exact output format with tables
- Handle edge cases explicitly
- Use consistent terminology

❌ **DON'T**:
- Leave thresholds vague ("high cost")
- Assume Claude knows domain knowledge
- Skip edge case handling
- Use ambiguous phrasing
- Forget to specify units ($, %, count)

### Example Quality

✅ **DO**:
- Use realistic data values
- Show full analysis process
- Include "why" explanations
- Cover diverse scenarios
- Demonstrate proper formatting

❌ **DON'T**:
- Use trivial/unrealistic examples
- Show only happy paths
- Skip edge cases
- Leave output incomplete

### Testing

✅ **DO**:
- Test all calculation formulas
- Validate threshold logic
- Check edge cases (zero, null, negative)
- Verify file structure
- Compare to original analyzer

❌ **DON'T**:
- Skip validation tests
- Assume logic is correct
- Test only happy paths
- Forget integration tests

## Common Patterns

### Threshold-Based Recommendations

```markdown
## Recommendation: [Action]

**Criteria** (ALL must be met):
1. [Metric] [operator] [threshold]
2. [Metric] [operator] [threshold]
3. [Condition]

**Example**:
- Cost ≥ $100
- ROAS < 1.5
- Match type = BROAD
```

### Comparative Analysis

```markdown
## Analysis: Compare [A] vs [B]

Calculate performance for each:
- [A] CPA: `[A_cost] / [A_conversions]`
- [B] CPA: `[B_cost] / [B_conversions]`

**Recommend [A] if**: [A_CPA] < [B_CPA] × 0.8 (20%+ better)
**Recommend [B] if**: [B_CPA] < [A_CPA] × 0.8
**No change if**: CPAs are within 20% of each other
```

### Multi-Factor Scoring

```markdown
## Scoring Methodology

Assign points for each factor:
- Quality Score ≥8: +2 points
- CPA below average: +1 point
- ROAS ≥2.0: +2 points
- CTR above 5%: +1 point

**HIGH Priority**: Score ≥4
**MEDIUM Priority**: Score 2-3
**LOW Priority**: Score 1
**No Action**: Score 0
```

## Troubleshooting

### Skill Doesn't Load
- Check `skill.json` is valid JSON
- Verify all required files exist
- Ensure file names match exactly
- Check version format (X.Y.Z)

### Incorrect Recommendations
- Review `examples.md` - may need more diverse scenarios
- Check prompt specificity - be more explicit about criteria
- Validate calculations in tests
- Compare to original analyzer output

### Inconsistent Output Format
- Define exact markdown structure in `prompt.md`
- Show complete example output in `examples.md`
- Use tables for structured data
- Specify heading levels precisely

### MCP Tool Errors
- Verify tool names in `requires_mcp_tools`
- Check MCP server is running
- Validate tool parameters in prompt
- Test tools independently first

## Migration Checklist

When converting an analyzer to a skill:

- [ ] Extract business logic to `docs/analyzer_patterns/`
- [ ] Create `skills/{name}/` directory
- [ ] Write `skill.json` with metadata
- [ ] Create `prompt.md` with detailed methodology
- [ ] Add `examples.md` with 5+ scenarios
- [ ] Write `README.md` user documentation
- [ ] Create test suite in `tests/test_{name}_skill.py`
- [ ] Run tests: `pytest tests/test_{name}_skill.py -v`
- [ ] Validate with real data via Claude
- [ ] Compare output to original analyzer
- [ ] Package skill: `python scripts/package_skill.py {name}`
- [ ] Document lessons learned
- [ ] Update plan with checkmarks

## Next Steps

After successfully converting your first skill (KeywordMatchAnalyzer), use it as a template for the remaining 23 analyzers. The pattern is now established:

1. **Priority Tier 1** (5 skills): Core cost efficiency analyzers
2. **Priority Tier 2** (10 skills): Advanced optimization analyzers
3. **Priority Tier 3** (9 skills): Specialized analysis analyzers

See [Phase 4](#) and [Phase 5](#) in the implementation plan for the full conversion roadmap.
