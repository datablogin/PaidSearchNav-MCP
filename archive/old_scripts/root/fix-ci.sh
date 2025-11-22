#!/bin/bash
# Smart CI fix script using --resume

# Function to fix CI failures
fix_ci_smart() {
    echo "🔧 Checking for CI failures..."
    
    # Check if we have a recent session
    if claude-code sessions list | grep -q "Active.*today"; then
        echo "📌 Resuming previous session..."
        claude-code . --resume-last -p "Fix any failing CI tests and linting issues. Run pytest and ruff locally to verify fixes."
    else
        echo "🆕 Starting fresh session..."
        claude-code . -p "Pull latest changes and fix failing CI tests in the current PR. Focus only on test failures."
    fi
}

# Function to implement review feedback
fix_review() {
    echo "📝 Implementing review feedback..."
    
    # Get latest PR comments
    gh pr view --comments > /tmp/pr-comments.txt
    
    # Resume with context
    claude-code . --resume-last -p "Implement the review feedback from the PR comments. Here are the latest comments: $(cat /tmp/pr-comments.txt)"
}

# Main menu
case "${1:-}" in
    ci)
        fix_ci_smart
        ;;
    review)
        fix_review
        ;;
    both)
        fix_ci_smart
        echo "✅ CI fixed, now handling reviews..."
        fix_review
        ;;
    *)
        echo "Usage: $0 {ci|review|both}"
        echo "  ci     - Fix CI failures"
        echo "  review - Implement review feedback"
        echo "  both   - Fix CI then implement reviews"
        exit 1
        ;;
esac