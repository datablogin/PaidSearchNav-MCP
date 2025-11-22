# PaidSearchNav Archive

This directory contains code and documentation from the original monolithic PaidSearchNav application before the MCP + Skills refactoring (November 2025).

## What's Here

- `old_app/` - Original Python application with 24 analyzers
- `old_tests/` - Test files from monolithic app (24 test files)
- `test_data/` - CSV/JSON test data files
- `old_scripts/` - Legacy utility scripts
- `old_docs/` - Documentation for old architecture (30 markdown files)
- `old_configs/` - Docker, environment, and deployment configs
- `old_infrastructure/` - AWS, GitHub workflows, and deployment code

## Why Archived

The PaidSearchNav refactoring separated:
- **Data connectivity** → MCP Server (src/paidsearchnav_mcp/)
- **Analysis logic** → Claude Skills (separate repository)

This resulted in:
- 87% reduction in deployment size (1.5GB → 200MB)
- 8 dependencies vs 62
- Faster iteration on analysis logic
- Standards-based integration (MCP protocol)

## Useful References

When converting analyzers to Skills, refer to:
- `old_app/paidsearchnav/analyzers/` - Original analyzer implementations
- `old_tests/` - Test cases showing expected behavior
- `test_data/` - Sample data for testing

## DO NOT Use This Code Directly

This code is for reference only. The new architecture is fundamentally different. Extract patterns and logic, don't copy/paste code.

## Archive Date

November 22, 2025 - Phase 0 of MCP Skills Refactoring Implementation
