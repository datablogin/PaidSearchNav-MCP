# Developer Advice for Multi-Agent Coordination

This document provides guidance for efficiently directing AI agents to work on PaidSearchNav issues using our coordination system.

## 🎯 Quick Start: Prompting Agents

### Standard Prompt Template

```
Please work on Issue #{number} - {title}.

Before starting:
1. Check STATUS.md to confirm the issue is available
2. Review CONTRIBUTING.md for workflow guidelines
3. Follow ARCHITECTURE.md for technical specifications

Create your feature branch: feature/issue-{number}-{short-description}
```

### Concise Version

```
Work on Issue #{number} ({title}) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
```

## 📋 Example Prompts by Phase

### Phase 1: Infrastructure (Can Work in Parallel)

```
Work on Issue #10 (Google Ads API Integration) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
```

```
Work on Issue #11 (OAuth2 Token Manager) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
```

```
Work on Issue #15 (Data Storage & History) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
```

```
Work on Issue #16 (Logging & Monitoring) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
```

### Phase 2: Core Analyzers (Requires Issue #10)

```
Work on Issue #2 (Keyword Match Type Audit) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
Note: This depends on Issue #10 being completed first.
```

```
Work on Issue #3 (Search Terms Analysis) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
Note: This depends on Issue #10 being completed first.
```

```
Work on Issue #4 (Geo Performance Dashboard) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
Note: This depends on Issues #10 and #15 being completed first.
```

### Phase 3: Advanced Features

```
Work on Issue #5 (Local Intent Keywords) following STATUS.md/CONTRIBUTING.md/ARCHITECTURE.md guidelines.
Note: This depends on Issues #2 and #3 being completed first.
```

## 🔄 What Happens Automatically

When you use these prompts, the agent will automatically:

1. **Check STATUS.md** to verify the issue is available
2. **Comment on GitHub** to claim the issue
3. **Create the correct branch** name (feature/issue-X-description)
4. **Update STATUS.md** with their assignment and branch
5. **Create a draft PR** early to show progress
6. **Follow file ownership** rules to avoid conflicts
7. **Run tests and linting** before pushing
8. **Update documentation** as needed

## 📊 Recommended Work Order

### Parallel Work Opportunities

You can assign multiple agents to work simultaneously on:

**Phase 1 Infrastructure:**
- Issue #10 (Google Ads API) - Agent 1
- Issue #11 (OAuth2) - Agent 2
- Issue #15 (Storage) - Agent 3
- Issue #16 (Logging) - Agent 4

**Phase 2 Analyzers** (after #10 completes):
- Issue #2 (Keyword Match) - Agent 1
- Issue #3 (Search Terms) - Agent 2
- Issue #6 (PMax Analyzer) - Agent 3
- Issue #4 (Geo Dashboard) - Agent 4 (also needs #15)

### Sequential Dependencies

Some issues must wait for others:
- Issue #5 depends on #2 and #3
- Issue #7 depends on #10
- Issue #8 depends on #2-7
- Issue #12 depends on #10 and #11
- Issue #14 depends on #2-8

## 💡 Best Practices

### DO:
- ✅ Always reference the coordination files in your prompt
- ✅ Include the issue number and title
- ✅ Mention dependencies if applicable
- ✅ Trust the process - agents will follow the guidelines
- ✅ Assign Phase 1 issues first to unblock others

### DON'T:
- ❌ Assign the same issue to multiple agents
- ❌ Skip checking STATUS.md before assignment
- ❌ Forget about dependencies between issues
- ❌ Overcomplicate the prompt with detailed instructions

## 🚨 Troubleshooting

### If an agent says an issue is already taken:
1. Check STATUS.md for current assignments
2. Check GitHub issue comments
3. Look for existing branches: `git branch -r | grep issue-X`

### If there are conflicts:
1. Check the file ownership map in STATUS.md
2. Ensure agents are syncing with develop regularly
3. Use draft PRs to communicate changes early

### If an agent is blocked:
1. Check if dependencies are completed
2. Have them update STATUS.md with blocked status
3. Assign them a different issue while waiting

## 📝 Monitoring Progress

To check overall project status:

```bash
# See all feature branches
git branch -r | grep feature/issue

# Check PR status
gh pr list

# View specific PR
gh pr view {number}
```

Or simply ask an agent:
```
Please check STATUS.md and give me a summary of current development progress.
```

## 🎉 Success Metrics

You'll know the coordination is working when:
- No two agents work on the same issue
- PRs don't have major conflicts
- Dependencies are respected
- STATUS.md accurately reflects reality
- Development progresses smoothly

## 📚 Additional Resources

- **STATUS.md**: Current work assignments and progress
- **CONTRIBUTING.md**: Detailed development workflow
- **ARCHITECTURE.md**: Technical specifications and interfaces
- **CLAUDE.md**: Project context and requirements

Remember: The coordination system is designed to be self-managing. Trust the process and keep your prompts simple!