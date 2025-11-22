# Contributing to PaidSearchNav MCP Server

Thank you for your interest in contributing to the PaidSearchNav MCP Server! This document provides guidelines for contributing to the MCP server implementation.

> **Note**: This repository contains the MCP server only. The original monolithic application has been archived to `archive/`. See [archive/README.md](archive/README.md) for historical context.

## 🚀 Quick Start

1. **Check GitHub Issues** to see what work is available
2. **Claim an issue** by commenting on GitHub
3. **Create a feature branch** following our naming convention
4. **Create a draft PR** early to signal progress
5. **Run tests and quality checks** before requesting review

## 📋 Development Workflow

### 1. Claiming an Issue

Before starting work:
1. Check GitHub Issues to ensure the issue isn't already being worked on
2. Comment on the GitHub issue: "I'm starting work on this issue"
3. Wait for confirmation if another contributor is already assigned

### 2. Branch Naming Convention

Always create branches with this format:
```
feature/issue-{number}-{short-description}
```

Examples:
- `feature/issue-2-keyword-match-audit`
- `feature/issue-10-google-ads-api`
- `feature/issue-13-environment-management`

### 3. Working Process

```bash
# IMPORTANT: Always start from main branch (NOT develop)
git checkout main
git pull origin main

# Create your feature branch
git checkout -b feature/issue-X-description

# Work on your changes
# ... make changes ...

# Commit with conventional commits (selective add, not .)
git add path/to/specific/file.py
git add tests/for/specific/file.py
git commit -m "feat: implement keyword match type analyzer

- Add KeywordAnalyzer class
- Implement match type distribution logic
- Add unit tests for analyzer"

# Push and create draft PR early
git push -u origin feature/issue-X-description
```

### 4. Pull Request Guidelines

1. **Create Draft PR Early**: As soon as you have initial commits
2. **Link to Issue**: Use "Closes #X" in PR description
3. **Update STATUS.md**: Mark your issue as "PR Created"
4. **Keep PR Focused**: One issue per PR
5. **Write Tests**: All new code needs tests
6. **Update Docs**: If adding new features

### 5. Commit Message Format

We use conventional commits:

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

## 🔄 Avoiding Conflicts

### File Ownership

Check `STATUS.md` for the file ownership map. Each issue typically owns specific files:

- **Don't modify** files owned by other issues
- **Coordinate** when you need to modify shared files
- **Communicate** in PR comments about any conflicts

### Shared Files

These files require extra coordination:
- `paidsearchnav/core/interfaces.py`
- `paidsearchnav/core/models/`
- `.github/workflows/`

When modifying shared files:
1. Comment in the PR about what you're changing
2. Keep changes minimal and focused
3. Consider creating a separate PR for shared file changes

### Syncing with Main

**CRITICAL**: Regularly sync your branch with main (at least daily):

```bash
# Option 1: Fetch and merge
git fetch origin main
git merge origin/main

# Option 2: Pull
git pull origin main

# Option 3: Use git alias (recommended)
git config --global alias.sync '!git fetch origin main && git merge origin/main'
git sync  # Use the alias
```

### Branch Management Best Practices

⚠️ **IMPORTANT CHANGES**:
1. **NEVER** branch from `develop` - it's deprecated and often out of sync
2. **ALWAYS** create new branches from `main`
3. **CHECK** STATUS.md on GitHub (not local copy) for latest updates
4. **SYNC** with main before starting work each day

### Preventing Stale Branch Issues

To avoid the problems caused by stale branches:

1. **Daily Sync Routine**:
   ```bash
   # Start of each work session
   git checkout main
   git pull origin main
   git checkout your-feature-branch
   git merge main
   ```

2. **Before Creating PRs**:
   ```bash
   # Always sync before pushing final changes
   git fetch origin main
   git merge origin/main
   # Resolve any conflicts
   git push
   ```

3. **Verify Branch Status**:
   ```bash
   # Check how far behind main you are
   git fetch origin
   git log --oneline HEAD..origin/main
   ```

## 🧪 Testing Requirements

### Unit Tests
- Required for all new code
- Use pytest
- Aim for >80% coverage
- Mock external dependencies

### Integration Tests
- Required for API integrations
- Test with real Google Ads sandbox account
- Document any test data requirements

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/analyzers/test_keyword_match.py

# Run with coverage
pytest --cov=paidsearchnav --cov-report=html
```

## 📝 Documentation

### Code Documentation
- Add docstrings to all classes and methods
- Use Google-style docstrings
- Include examples for complex functions

### User Documentation
- Update README.md for new features
- Add configuration examples to docs/
- Document any new dependencies

### Git Workflow Documentation
- Keep STATUS.md updated with your progress
- Document any branch management issues in PRs
- Update CLAUDE.md if workflow changes are needed

## 🔍 Code Review Checklist

Before marking PR as ready:

- [ ] All tests pass
- [ ] Code follows project style (ruff)
- [ ] Documentation updated
- [ ] STATUS.md updated
- [ ] No conflicts with main
- [ ] Linked to GitHub issue
- [ ] Follows file ownership rules
- [ ] Security review completed (see below)

## 🔐 Security Review Requirements

All code changes must pass security review before merging. This is especially critical for:

### High-Risk Areas
1. **Authentication & Authorization** (OAuth2, API keys)
2. **Database Operations** (SQL injection prevention)
3. **External API Calls** (data validation, rate limiting)
4. **File Operations** (path traversal, permissions)
5. **Configuration & Secrets** (credential storage, logging)

### Security Checklist
Before submitting your PR, ensure:

- [ ] **No hardcoded secrets**: API keys, passwords, tokens must use environment variables
- [ ] **Input validation**: All user inputs and API responses validated
- [ ] **SQL injection prevention**: Use parameterized queries, never string concatenation
- [ ] **Secure credential storage**: Use SecretStr for sensitive config fields
- [ ] **Safe logging**: No credentials or PII in logs
- [ ] **File permissions**: Appropriate permissions for created files (especially logs)
- [ ] **Path validation**: Prevent directory traversal attacks
- [ ] **Error handling**: Don't expose sensitive information in error messages
- [ ] **Dependencies**: No known vulnerabilities in new dependencies

### Required for Security-Critical PRs
If your PR touches any of these areas, additional review is required:

1. **Authentication Changes** (Issues #11, #25)
   - OAuth2 flow modifications
   - Token storage/retrieval
   - Browser vs server authentication

2. **Database Operations** (Issues #15, #28, #35, #36)
   - SQL query construction
   - Connection string handling
   - Session management

3. **Configuration Management** (Issues #13, #53)
   - Environment variable handling
   - Secret storage patterns
   - Configuration validation

4. **Logging System** (Issues #16, #42, #43)
   - Log sanitization
   - File permissions
   - Credential filtering

### Security Testing
- Write tests that verify security controls
- Include negative test cases (invalid inputs)
- Test with malicious inputs where applicable
- Verify error messages don't leak sensitive data

## 🚨 Emergency Procedures

### If You Break Something
1. Don't panic!
2. Comment on the PR immediately
3. If on main branch, revert the commit
4. Update STATUS.md with the issue

### If You're Blocked
1. Update STATUS.md with blocked status
2. Comment on the blocking issue
3. Look for another issue to work on
4. Help review other PRs

### If Your Branch is Out of Sync
1. Don't panic - this is common
2. Sync with main: `git fetch origin main && git merge origin/main`
3. Resolve any conflicts carefully
4. Test thoroughly after merging
5. Update STATUS.md if major changes affected your work

## 💬 Communication

### Where to Communicate
- **Issue Comments**: For issue-specific discussions
- **PR Comments**: For code-specific feedback
- **STATUS.md**: For general project status

### What to Communicate
- When you start/stop work
- If you're blocked
- If you need to modify shared files
- Any architectural decisions

## 🎯 Priority Guidelines

Follow the priority order in CLAUDE.md:

1. **Phase 1**: Infrastructure (API, Auth, Storage)
2. **Phase 2**: Core Features (Analyzers)
3. **Phase 3**: Advanced Features (Reports, Automation)

## ✅ Definition of Done

An issue is considered done when:

1. All acceptance criteria met
2. Tests written and passing
3. Documentation updated
4. PR approved and merged
5. STATUS.md updated to show completion

## 🙋 Getting Help

- Check existing issues for similar problems
- Read ARCHITECTURE.md for design decisions
- Look at existing code for patterns
- Comment on issues for clarification

Remember: It's better to over-communicate than to create conflicts!