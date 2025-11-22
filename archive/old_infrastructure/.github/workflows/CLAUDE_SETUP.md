# Claude Code GitHub Actions Setup

## Error: "Credit balance is too low"

This error indicates one of the following issues:

1. **No API Key Configured**: The `ANTHROPIC_API_KEY` secret is not set in your GitHub repository.
2. **Insufficient Credits**: The API key doesn't have enough credits to run Claude.

## Setup Instructions

### 1. Get an Anthropic API Key

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Navigate to API Keys section
3. Create a new API key
4. Ensure your account has sufficient credits

### 2. Add the API Key to GitHub Secrets

1. Go to your repository settings
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `ANTHROPIC_API_KEY`
5. Value: Your Anthropic API key
6. Click "Add secret"

### 3. Verify Setup

The workflows have been updated with error handling:
- They check if the API key is configured before running
- They continue on error to prevent blocking CI
- They provide helpful warning messages

## Workflow Files

- **`.github/workflows/claude.yml`**: Responds to @claude mentions in issues/PRs
- **`.github/workflows/claude-code-review.yml`**: Automatically reviews pull requests

## Optional: Disable Claude Reviews

To temporarily disable Claude reviews without removing the workflows:

1. Don't set the `ANTHROPIC_API_KEY` secret, or
2. Add `[skip-review]` to your PR title

## Troubleshooting

If you continue to see errors:
1. Verify your API key is valid
2. Check your Anthropic account has credits
3. Review the GitHub Actions logs for detailed error messages