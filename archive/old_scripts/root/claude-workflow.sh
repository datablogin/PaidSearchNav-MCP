#!/bin/bash
# Claude Code workflow automation script

# Function to start work on a new issue
start_issue() {
    local issue_number=$1
    if [ -z "$issue_number" ]; then
        echo "Usage: start_issue <issue_number>"
        return 1
    fi
    
    echo "Starting work on issue #$issue_number..."
    
    # Use Claude Code with predefined prompt
    claude-code . --prompt "Checkout main, pull latest, and start working on GitHub issue #$issue_number. Create feature branch and implement the requirements. When done, create a PR that closes the issue."
}

# Function to fix CI/review issues
fix_ci() {
    echo "Fixing CI and review feedback..."
    
    # Use Claude Code to fix issues
    claude-code . --prompt "Implement the Claude review recommendations and fix any CI test failures for the current PR. Run tests and linting before committing."
}

# Function to complete work and start fresh
next_issue() {
    local next_issue=$1
    
    echo "Completing current work and starting issue #$next_issue..."
    
    # Exit current session and start new one
    claude-code . --prompt "Commit and push any remaining changes." --then exit
    
    # Start fresh session for next issue
    start_issue $next_issue
}

# Export functions for use in shell
export -f start_issue
export -f fix_ci
export -f next_issue

# Add to your .bashrc or .zshrc:
# source /path/to/claude-workflow.sh