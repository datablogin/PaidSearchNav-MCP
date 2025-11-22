#!/bin/bash

# Claude Code Local Review Script
# Enhanced version that matches GitHub Action functionality
# Supports structured prompts, focus areas, and multiple output modes

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
FOCUS_AREAS=""
MODEL=""
POST_COMMENT=true
OUTPUT_MODE="comment"
DRY_RUN=false
MAX_DIFF_LINES=500  # Maximum diff lines to include for review

# Get current branch to return to later
ORIGINAL_BRANCH=$(git branch --show-current)

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS] [PR_NUMBER]"
    echo "  PR_NUMBER: Optional PR number to review (defaults to current PR)"
    echo ""
    echo "Options:"
    echo "  --focus AREA        Focus review on specific area:"
    echo "                      security, performance, testing, google-ads, style"
    echo "  --model MODEL       Use specific Claude model"
    echo "  --save-file         Save review to file instead of posting as comment (default: post comment)"
    echo "  --draft-comment     Post review as draft PR comment"
    echo "  --max-diff-lines N  Maximum diff lines to include (default: 500, 0 = no limit)"
    echo "  --dry-run          Show what would be reviewed without calling Claude"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                               # Review current PR and post as comment"
    echo "  $0 54                           # Review PR #54 and post as comment"
    echo "  $0 --focus security 54          # Focus on security review and post as comment"
    echo "  $0 --focus google-ads 54        # Focus on Google Ads API patterns and post as comment"
    echo "  $0 --save-file 54               # Save review to file instead of posting"
    echo "  $0 --draft-comment 54           # Post as draft PR comment"
    echo "  $0 --max-diff-lines 1000 54     # Include up to 1000 diff lines"
    echo "  $0 --max-diff-lines 0 54        # Include full diff (no limit)"
    echo "  $0 --dry-run 54                 # Preview what would be reviewed"
    exit 1
}

# Check dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command -v gh &> /dev/null; then
        missing_deps+=("GitHub CLI (gh) - https://cli.github.com/")
    fi
    
    if ! command -v claude &> /dev/null; then
        missing_deps+=("Claude Code - https://docs.anthropic.com/en/docs/claude-code")
    fi
    
    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq - https://jqlang.github.io/jq/")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo -e "${RED}Error: Missing dependencies:${NC}"
        printf '  - %s\n' "${missing_deps[@]}"
        echo ""
        echo "Please install the missing dependencies and try again."
        exit 1
    fi
}

check_dependencies

# Note: Removed Claude connectivity test function - not needed for local Claude Code usage

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --focus)
            FOCUS_AREAS="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --save-file)
            POST_COMMENT=false
            OUTPUT_MODE="file"
            shift
            ;;
        --draft-comment)
            POST_COMMENT=true
            OUTPUT_MODE="draft-comment"
            shift
            ;;
        --max-diff-lines)
            MAX_DIFF_LINES="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            usage
            ;;
        -*)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            ;;
        *)
            if [[ $1 =~ ^[0-9]+$ ]]; then
                PR_NUM=$1
            else
                echo -e "${RED}Error: Invalid PR number: $1${NC}"
                usage
            fi
            shift
            ;;
    esac
done

# Note: Removed Claude connectivity test as it's not needed for local Claude Code usage

# Get PR number if not provided
if [ -z "$PR_NUM" ]; then
    PR_NUM=$(gh pr view --json number -q .number 2>/dev/null || echo "")
    if [ -z "$PR_NUM" ]; then
        echo -e "${RED}Error: Not currently on a PR branch${NC}"
        echo "Please specify a PR number or checkout a PR branch"
        usage
    fi
fi

# Validate PR exists
if ! gh pr view "$PR_NUM" > /dev/null 2>&1; then
    echo -e "${RED}Error: PR #$PR_NUM not found${NC}"
    exit 1
fi

# Helper function to detect Google Ads API files
has_google_ads_files() {
    gh pr diff "$PR_NUM" --name-only | grep -E "(platforms/google|analyzers|google_ads)" > /dev/null 2>&1
}

# Helper function to count significant changes
count_significant_changes() {
    local additions=$(gh pr view "$PR_NUM" --json additions -q .additions)
    local deletions=$(gh pr view "$PR_NUM" --json deletions -q .deletions)
    echo $((additions + deletions))
}

# Helper function to create intelligent diff summary
create_diff_summary() {
    local pr_num="$1"
    local max_lines="$2"
    
    if [ "$max_lines" -eq 0 ]; then
        # No limit - include full diff
        gh pr diff "$pr_num"
        return
    fi
    
    local full_diff
    full_diff=$(gh pr diff "$pr_num")
    local diff_line_count
    diff_line_count=$(echo "$full_diff" | wc -l | tr -d ' ')
    
    if [ "$diff_line_count" -le "$max_lines" ]; then
        # Diff is within limits - include it all
        echo "$full_diff"
    else
        # Diff is too long - create intelligent summary
        echo "### ⚠️ Large Diff Summary (${diff_line_count} lines total, showing first ${max_lines} lines)"
        echo ""
        echo "\`\`\`diff"
        echo "$full_diff" | head -n "$max_lines"
        echo ""
        echo "... (diff truncated - ${diff_line_count} total lines, showing first ${max_lines})"
        local repo_owner
        local repo_name
        repo_owner=$(gh repo view --json owner -q '.owner.login')
        repo_name=$(gh repo view --json name -q '.name')
        echo "Full diff available at: https://github.com/${repo_owner}/${repo_name}/pull/${pr_num}/files"
        echo "\`\`\`"
    fi
}

# Helper function to generate review prompt based on focus and file types
generate_review_prompt() {
    local base_prompt="Please review this pull request and provide feedback on:
- Code quality and best practices
- Potential bugs or issues
- Performance considerations
- Security concerns
- Test coverage

Be constructive and helpful in your feedback."

    local additional_prompt=""
    
    # Add Google Ads API specific prompts if relevant files are detected
    if has_google_ads_files || [[ "$FOCUS_AREAS" == *"google-ads"* ]]; then
        additional_prompt="${additional_prompt}

For Google Ads API code, also review:
- Proper API client initialization and authentication handling
- Correct usage of Google Ads API v20 query structure and field selection
- Rate limiting and circuit breaker implementation
- Error handling for API exceptions and quota limits
- Proper pagination handling for large result sets
- Secure handling of API credentials and tokens
- Data validation and sanitization for user inputs"
    fi
    
    # Add focus area specific prompts
    case "$FOCUS_AREAS" in
        security)
            additional_prompt="${additional_prompt}

Focus specifically on security concerns:
- Input validation and sanitization
- Authentication and authorization
- Sensitive data handling
- Potential injection vulnerabilities"
            ;;
        performance)
            additional_prompt="${additional_prompt}

Focus specifically on performance:
- Algorithm efficiency and time complexity
- Memory usage optimization
- Database query efficiency
- Caching opportunities"
            ;;
        testing)
            additional_prompt="${additional_prompt}

Focus specifically on testing:
- Test coverage completeness
- Test quality and maintainability
- Edge case coverage
- Mock and fixture usage"
            ;;
        style)
            additional_prompt="${additional_prompt}

Focus specifically on code style:
- Consistency with project conventions
- Code readability and maintainability
- Documentation quality
- Naming conventions"
            ;;
        google-ads)
            additional_prompt="${additional_prompt}

Focus specifically on Google Ads API integration:
- API client patterns and best practices
- Authentication and authorization flows
- Data parsing and transformation logic
- Error handling and retry mechanisms
- Performance and rate limiting considerations"
            ;;
    esac
    
    echo "${base_prompt}${additional_prompt}"
}

# Get comprehensive PR info
PR_INFO=$(gh pr view "$PR_NUM" --json title,author,baseRefName,headRefName,additions,deletions,changedFiles,commits)
PR_TITLE=$(echo "$PR_INFO" | jq -r .title)
PR_AUTHOR=$(echo "$PR_INFO" | jq -r .author.login)
PR_BRANCH=$(echo "$PR_INFO" | jq -r .headRefName)
PR_BASE_BRANCH=$(echo "$PR_INFO" | jq -r .baseRefName)
PR_ADDITIONS=$(echo "$PR_INFO" | jq -r .additions)
PR_DELETIONS=$(echo "$PR_INFO" | jq -r .deletions)
PR_CHANGED_FILES=$(echo "$PR_INFO" | jq -r .changedFiles)
PR_COMMITS=$(echo "$PR_INFO" | jq -r '.commits | length')

echo -e "${GREEN}Reviewing PR #$PR_NUM: $PR_TITLE${NC}"
echo -e "Author: $PR_AUTHOR"
echo -e "Branch: $PR_BRANCH → $PR_BASE_BRANCH"
echo -e "Changes: ${GREEN}+$PR_ADDITIONS${NC} ${RED}-$PR_DELETIONS${NC} lines across $PR_CHANGED_FILES files"
echo -e "Commits: $PR_COMMITS"

# Show focus area if specified
if [ -n "$FOCUS_AREAS" ]; then
    echo -e "Focus: ${BLUE}$FOCUS_AREAS${NC}"
fi

echo ""


# Checkout PR if not already on it
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ]; then
    echo -e "${YELLOW}Checking out PR branch...${NC}"
    gh pr checkout "$PR_NUM"
fi

# Generate the review prompt
REVIEW_PROMPT=$(generate_review_prompt)

# Prepare context information with intelligent diff handling
echo -e "${BLUE}Preparing PR context (max diff lines: $MAX_DIFF_LINES)...${NC}"

PR_CONTEXT="
### PR Context
- **Title:** $PR_TITLE
- **Author:** $PR_AUTHOR  
- **Branch:** $PR_BRANCH → $PR_BASE_BRANCH
- **Additions:** $PR_ADDITIONS lines
- **Deletions:** $PR_DELETIONS lines
- **Files Changed:** $PR_CHANGED_FILES
- **Commits:** $PR_COMMITS

### Files in this PR:
\`\`\`
$(gh pr diff "$PR_NUM" --name-only)
\`\`\`

### Code Changes:
$(create_diff_summary "$PR_NUM" "$MAX_DIFF_LINES")
"

# Dry run mode - show what would be reviewed
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}DRY RUN MODE - Preview of review context:${NC}"
    echo ""
    echo "Files to be reviewed:"
    gh pr diff "$PR_NUM" --name-only | sed 's/^/  - /'
    echo ""
    echo "Generated prompt:"
    echo "$(generate_review_prompt)" | sed 's/^/  /'
    echo ""
    echo -e "${YELLOW}Diff handling: Max lines set to $MAX_DIFF_LINES${NC}"
    echo -e "${YELLOW}Use without --dry-run to perform actual review${NC}"
    exit 0
fi


# Execute review based on output mode
case "$OUTPUT_MODE" in
    "comment"|"draft-comment")
        echo -e "${YELLOW}Running Claude review and posting to PR...${NC}"
        
        # Create temporary file for review
        TEMP_FILE=$(mktemp)
        
        # Add context and prompt to temp file
        cat > "$TEMP_FILE" << EOF
$PR_CONTEXT

---

$REVIEW_PROMPT
EOF
        
        # Run Claude and capture output
        echo -e "${BLUE}Calling Claude for review...${NC}"
        if claude chat < "$TEMP_FILE" > "${TEMP_FILE}.output" 2>&1; then
            # Prepare comment body with header (exclude full context to save space)
            COMMENT_FILE=$(mktemp)
            cat > "$COMMENT_FILE" << EOF
# 🔍 Claude Code Review

## Review Feedback

$(cat "${TEMP_FILE}.output")

---
*Review generated by Claude Local PR Review Tool*
EOF
            
            # Post comment and get URL
            if [ "$OUTPUT_MODE" = "draft-comment" ]; then
                COMMENT_URL=$(gh pr comment "$PR_NUM" --body-file "$COMMENT_FILE" --draft 2>&1 | grep -o 'https://.*' || echo "")
                echo -e "${GREEN}✓ Review posted as draft PR comment${NC}"
            else
                COMMENT_URL=$(gh pr comment "$PR_NUM" --body-file "$COMMENT_FILE" 2>&1 | grep -o 'https://.*' || echo "")
                echo -e "${GREEN}✓ Review posted as PR comment${NC}"
            fi
            
            if [ -n "$COMMENT_URL" ]; then
                echo "$COMMENT_URL"
            fi
            
            # Show summary
            echo ""
            echo "Review Summary:"
            echo "---------------"
            if [ -s "${TEMP_FILE}.output" ]; then
                # File exists and has content
                head -n 20 "${TEMP_FILE}.output" | sed 's/^/  /'
                line_count=$(wc -l < "${TEMP_FILE}.output")
                if [ "$line_count" -gt 20 ]; then
                    echo "  ..."
                    echo "  (Showing first 20 lines of $line_count total)"
                fi
            else
                echo "  Review completed successfully but output format unexpected."
            fi
            
            rm -f "$COMMENT_FILE"
        else
            echo -e "${RED}✗ Claude review failed${NC}"
            echo "Error details:"
            if [ -f "${TEMP_FILE}.output" ]; then
                cat "${TEMP_FILE}.output" | sed 's/^/  /'
            else
                echo "  No output file generated"
            fi
            echo ""
            echo "Possible causes:"
            echo "  - Claude CLI not properly authenticated"
            echo "  - Network connectivity issues"
            echo "  - Input too large for Claude context"
            echo "  - Claude service temporarily unavailable"
            echo ""
            echo "Try running: claude auth login"
        fi
        
        rm -f "$TEMP_FILE" "${TEMP_FILE}.output"
        ;;
        
    "file")
        # Create output filename
        DATE=$(date +%Y%m%d_%H%M)
        OUTPUT_DIR="reviews/manual"
        FOCUS_SUFFIX=""
        if [ -n "$FOCUS_AREAS" ]; then
            FOCUS_SUFFIX="-${FOCUS_AREAS}"
        fi
        OUTPUT_FILE="$OUTPUT_DIR/pr-${PR_NUM}${FOCUS_SUFFIX}-${DATE}.md"
        
        # Ensure output directory exists
        mkdir -p "$OUTPUT_DIR"
        
        echo -e "${YELLOW}Running Claude review and saving to file...${NC}"
        
        # Create header for the review file (include full context for local files)
        cat > "$OUTPUT_FILE" << EOF
# 🔍 Claude Code Review: PR #$PR_NUM

**Title:** $PR_TITLE  
**Author:** $PR_AUTHOR  
**Date:** $(date +"%Y-%m-%d %H:%M:%S")  
**Branch:** $PR_BRANCH → $PR_BASE_BRANCH
**Focus:** ${FOCUS_AREAS:-"General review"}

$PR_CONTEXT

---

## Review Prompt Used

$REVIEW_PROMPT

---

## Claude Review Output

EOF
        
        # Create temp file with context and prompt
        TEMP_FILE=$(mktemp)
        cat > "$TEMP_FILE" << EOF
$PR_CONTEXT

---

$REVIEW_PROMPT
EOF
        
        # Run Claude and append to file
        if claude chat < "$TEMP_FILE" >> "$OUTPUT_FILE" 2>&1; then
            echo -e "${GREEN}✓ Review completed successfully${NC}"
            echo -e "${GREEN}✓ Saved to: $OUTPUT_FILE${NC}"
            
            # Show summary
            echo ""
            echo "Review Summary:"
            echo "---------------"
            # Extract first few lines of review output
            tail -n +25 "$OUTPUT_FILE" | head -n 20
            echo "..."
            echo ""
            echo -e "${YELLOW}Full review saved to: $OUTPUT_FILE${NC}"
            
            # Add token usage estimate
            if command -v wc &> /dev/null; then
                WORD_COUNT=$(wc -w < "$OUTPUT_FILE")
                TOKEN_ESTIMATE=$((WORD_COUNT * 4 / 3))
                echo -e "${BLUE}Estimated tokens used: ~$TOKEN_ESTIMATE${NC}"
            fi
        else
            echo -e "${RED}✗ Review failed${NC}"
            echo "Check $OUTPUT_FILE for error details"
        fi
        
        rm -f "$TEMP_FILE"
        ;;
esac

# Return to original branch if we switched
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ] && [ -n "$ORIGINAL_BRANCH" ]; then
    echo ""
    echo -e "${YELLOW}Returning to branch: $ORIGINAL_BRANCH${NC}"
    git checkout "$ORIGINAL_BRANCH"
fi

# Add helpful tips based on output mode
echo ""
case "$OUTPUT_MODE" in
    "comment"|"draft-comment")
        echo -e "${GREEN}Next steps:${NC}"
        echo "• Review the posted comment on GitHub"
        echo "• Address any issues raised in the review"
        echo "• Create follow-up issues if needed: gh issue create --title \"...\" --body \"...\""
        ;;
    "file")
        echo -e "${GREEN}Next steps:${NC}"
        echo "• Review the saved file: $OUTPUT_FILE"
        echo "• Extract concerns/issues for follow-up"
        echo "• Create GitHub issues: gh issue create --title \"...\" --body \"...\""
        echo "• Consider sharing the review with your team"
        ;;
esac

echo ""
echo -e "${BLUE}Enhanced Claude Review Script v2.0${NC}"
echo -e "For help: $0 --help"