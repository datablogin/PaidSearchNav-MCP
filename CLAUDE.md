# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PaidSearchNav is a Python-based tool for conducting quarterly Google Ads keyword audits, specifically designed for retail businesses with physical locations. The project focuses on cost efficiency analysis, keyword match type optimization, and Performance Max campaign integration.

### Business Context
- **Target Users**: Retail businesses with physical storefronts aiming to drive in-store visits and signups
- **Primary Goal**: Maximize cost efficiency by identifying wasted spend and optimizing targeting
- **Secondary Goal**: Ensure campaign functionality without internal conflicts (e.g., negative keywords blocking positive keywords)
- **Audit Frequency**: Quarterly (or on-demand as a premium service)
- **Key Focus**: Local intent optimization, especially "near me" searches and location-based performance

## Repository Information

- **GitHub URL**: https://github.com/datablogin/PaidSearchNav
- **Issues**: https://github.com/datablogin/PaidSearchNav/issues (15 feature issues created)
- **Main Branch**: Protected with CI/CD checks
- **Develop Branch**: DEPRECATED as of 2025-06-25 - Do not use. Always branch from main

## Development Commands

```bash
# Activate virtual environment (already created)
source .venv/bin/activate

# Install dependencies (using uv for faster installation)
uv pip install -e ".[dev,test]"

# Run tests
pytest

# Lint and format
ruff check .
ruff format .

# Type checking
mypy .

# Create feature branch for an issue (ALWAYS from main, not develop)
git checkout main
git pull origin main
git checkout -b feature/issue-{number}-{short-description}

# Push changes
git push -u origin feature/issue-{number}-{short-description}
```

## Standard Workflow Instructions

When starting work on a new issue:
1. Always checkout main and pull latest: `git checkout main && git pull origin main`
2. Create feature branch: `git checkout -b feature/issue-{number}-{short-description}`
3. Implement the issue requirements
4. Run tests and linting: `pytest && ruff check . && ruff format . && mypy .`
5. Commit changes with descriptive message
6. Create PR with title format: "Fix #{number}: {issue title}"
7. Include `closes #XXX` in PR description
8. Push to GitHub and create PR using `gh pr create`

When implementing Claude review feedback or fixing CI failures:
1. Pull latest changes if needed
2. Address all review comments
3. Fix any failing tests or linting issues
4. Commit with message like "Address review feedback and fix CI failures"
5. Push changes to update the PR

## Development Guidelines

### PR and Commit Best Practices
- Always use the issue number and issue name in the name of the PR
- Always add the issue number and issue title to the PR title
- **Always include closing keywords** in PR descriptions to auto-close issues:
  - Use `closes #XXX`, `fixes #XXX`, or `resolves #XXX` 
  - Example: "This PR closes #202 by implementing comprehensive database migration tests."

[... rest of the existing content remains the same ...]
- Always ask before using simulated or mock data with this codebase. Do not complete a task with simulated or mock data unless it is asked for specifically.  Attempt to access live data through Google Ads API, BigQuery, GA4 or any other Google property first before recommending simulated or mock data.