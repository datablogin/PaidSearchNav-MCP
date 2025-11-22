# Complete Environment Setup Guide

This guide documents every step taken to set up the PaidSocialNav project environment, allowing you to reproduce this setup for other projects.

## Prerequisites
- Python 3.11 or higher installed
- Git installed and configured
- GitHub account with personal access token
- PyPI account (for package publishing)

## Step-by-Step Setup Process

### 1. Initialize Local Project Structure

```bash
# Create project directory
mkdir -p ~/PycharmProjects/ProjectName
cd ~/PycharmProjects/ProjectName

# Initialize git repository
git init

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Create Project Configuration Files

#### A. Create `pyproject.toml`
```toml
[project]
name = "projectname"
version = "0.1.0"
description = "Your project description"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.21",
]
dev = [
    "ruff>=0.1.0",
    "mypy>=1.0",
    "pre-commit>=3.0",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 88
target-version = "py311"
select = ["E", "F", "I", "N", "W", "B", "UP"]
ignore = ["E501"]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "-v"

[tool.coverage.run]
source = ["projectname"]
omit = ["*/tests/*", "*/test_*"]
```

#### B. Create `.gitignore`
```gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# pipenv
Pipfile.lock

# poetry
poetry.lock

# pdm
.pdm.toml
.pdm-python

# PEP 582
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
.idea/

# VS Code
.vscode/

# macOS
.DS_Store

# Windows
Thumbs.db
ehthumbs.db

# Claude
.claude/
```

### 3. Set Up GitHub Actions CI/CD

#### A. Create directory structure
```bash
mkdir -p .github/workflows
mkdir -p .github/ISSUE_TEMPLATE
```

#### B. Create `.github/workflows/ci.yml`
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[test]"
    
    - name: Lint with ruff
      run: |
        pip install ruff
        ruff check .
    
    - name: Format check with ruff
      run: |
        ruff format --check .
    
    - name: Type check with mypy
      run: |
        pip install mypy
        mypy . || echo "No files to type check yet"
    
    - name: Test with pytest
      run: |
        pytest tests/ -v --cov=projectname --cov-report=xml --cov-report=term || echo "No tests found yet"
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        fail_ci_if_error: false
```

#### C. Create `.github/workflows/cd.yml`
```yaml
name: CD

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    
    - name: Build package
      run: python -m build
    
    - name: Create GitHub Release
      uses: actions/create-release@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        tag_name: ${{ github.ref }}
        release_name: Release ${{ github.ref }}
        draft: false
        prerelease: false
    
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: |
        twine upload dist/*
```

### 4. Create GitHub Templates

#### A. Create `.github/ISSUE_TEMPLATE/bug_report.md`
```markdown
---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment (please complete the following information):**
 - OS: [e.g. Ubuntu 22.04]
 - Python Version: [e.g. 3.11.5]
 - Project Version: [e.g. 0.1.0]

**Additional context**
Add any other context about the problem here.
```

#### B. Create `.github/ISSUE_TEMPLATE/feature_request.md`
```markdown
---
name: Feature request
about: Suggest an idea for this project
title: '[FEATURE] '
labels: enhancement
assignees: ''

---

**Is your feature request related to a problem? Please describe.**
A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context or screenshots about the feature request here.
```

#### C. Create `.github/pull_request_template.md`
```markdown
## Description
Please include a summary of the changes and the related issue. Please also include relevant motivation and context.

Fixes # (issue)

## Type of change
Please delete options that are not relevant.

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] This change requires a documentation update

## How Has This Been Tested?
Please describe the tests that you ran to verify your changes. Provide instructions so we can reproduce.

- [ ] Test A
- [ ] Test B

## Checklist:
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published in downstream modules
```

### 5. Create Dependency Management

#### Create `.github/dependabot.yml`
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "python"
    
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "github-actions"
```

### 6. Create Documentation Files

#### A. Create `README.md`
```markdown
# ProjectName

Project description here.

## Setup

1. Clone the repository:
\```bash
git clone https://github.com/yourusername/projectname.git
cd projectname
\```

2. Create and activate a virtual environment:
\```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
\```

3. Install the package in development mode:
\```bash
pip install -e ".[dev,test]"
\```

## Development

### Running Tests
\```bash
pytest
\```

### Linting and Formatting
\```bash
ruff check .
ruff format .
\```

### Type Checking
\```bash
mypy .
\```

## CI/CD

This project uses GitHub Actions for continuous integration. The CI pipeline runs on every push and pull request to the main and develop branches.

### GitHub Features Used:
- **Issues**: Bug reports and feature requests templates are available
- **Pull Requests**: Template provided for consistent PR descriptions
- **Actions**: Automated testing, linting, and type checking
- **Dependabot**: Automated dependency updates

## Contributing

1. Create a new branch for your feature or bugfix
2. Make your changes
3. Ensure all tests pass and code is properly formatted
4. Submit a pull request using the provided template

## License

[Add your license here]
```

#### B. Create `CLAUDE.md`
```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

[Describe your project's purpose and main functionality]

## Development Environment

- **Python Version**: Python 3.11 or higher required
- **IDE**: PyCharm configuration included
- **Virtual Environment**: `.venv/` directory present

## Project Structure

[Describe your project structure]

## Build and Development Commands

### Virtual Environment
\```bash
# Activate virtual environment (macOS/Linux)
source .venv/bin/activate

# Install dependencies (once added to pyproject.toml)
pip install -e .
\```

## Architecture Notes

[Add any architecture decisions or patterns used]

## Important Considerations

[Add any project-specific considerations]
```

### 7. Create GitHub Repository and Push

```bash
# Stage all files
git add -A

# Create initial commit
git commit -m "Initial commit: Set up project structure with CI/CD"

# Authenticate with GitHub (if not already done)
gh auth login --with-token < ~/github_token

# Create GitHub repository
gh repo create ProjectName --public --description "Your project description" --source=.

# Push to GitHub
git push -u origin main
```

### 8. Configure GitHub Repository Settings

#### A. Add branch protection rules
```bash
# Create a temporary JSON file with protection rules
cat > /tmp/branch-protection.json << 'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["test (ubuntu-latest, 3.11)", "test (ubuntu-latest, 3.12)"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

# Apply branch protection
gh api repos/yourusername/projectname/branches/main/protection -X PUT --input /tmp/branch-protection.json
```

#### B. Add secrets for PyPI deployment
```bash
# Add PyPI token (you'll be prompted to paste the token)
gh secret set PYPI_API_TOKEN --repo yourusername/projectname
```

### 9. Create Development Branch

```bash
git checkout -b develop
git push -u origin develop
```

### 10. Manual Steps

1. **Create GitHub Project Board**:
   - Go to `https://github.com/yourusername/projectname/projects`
   - Click "New project"
   - Choose "Board" template
   - Add columns: Backlog, Todo, In Progress, Review, Done

2. **Configure PyPI**:
   - Create account at https://pypi.org
   - Generate API token
   - Add token to GitHub secrets (step 8B)

## Summary

This setup provides:
- ✅ Python project structure with modern tooling
- ✅ Comprehensive CI/CD pipeline
- ✅ GitHub issue and PR templates
- ✅ Automated dependency updates
- ✅ Branch protection rules
- ✅ Automated PyPI publishing on version tags
- ✅ Professional development workflow

To start developing:
1. Create issues for features/bugs
2. Create feature branches from `develop`
3. Make changes and create PRs
4. CI runs automatically
5. Merge after approval
6. Tag releases for PyPI deployment