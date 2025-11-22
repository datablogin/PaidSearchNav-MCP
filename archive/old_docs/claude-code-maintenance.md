# Claude Code Maintenance Guide

## Common Issues and Solutions

### Auto-Update Corruption Problem

Claude Code's auto-update feature can corrupt the installation, causing the command to disappear or become unusable.

#### Symptoms of Corruption
- `claude` command not found despite being installed
- npm update/uninstall commands fail with `ENOTEMPTY` error:
  ```
  npm error code ENOTEMPTY
  npm error syscall rename
  npm error path /Users/robertwelborn/.nvm/versions/node/v24.1.0/lib/node_modules/@anthropic-ai/claude-code
  npm error errno -66
  ```
- Auto-update failed messages in Claude Code interface

#### Prevention: Disable Auto-Updates

Auto-updates are disabled on this machine using:
```bash
export DISABLE_AUTOUPDATER=1
```
This setting is permanent in `~/.zshrc`.

### Cleaning Up Corruption

#### Step 1: Identify Corruption
Try a normal update first:
```bash
npm update -g @anthropic-ai/claude-code
```

If you see the `ENOTEMPTY` error, proceed to cleanup.

#### Step 2: Force Clean Corrupted Installation
```bash
# Remove the entire corrupted anthropic directory
rm -rf ~/.nvm/versions/node/v24.1.0/lib/node_modules/@anthropic-ai

# Verify removal
ls ~/.nvm/versions/node/v24.1.0/lib/node_modules/ | grep anthropic
```

#### Step 3: Fresh Installation
```bash
# Install latest version
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

### Stable Access Solution

A wrapper script is installed at `~/.local/bin/claude` that provides stable access even during corruption issues.

The wrapper script:
1. Tries direct nvm path first
2. Falls back to PATH lookup
3. Initializes nvm as last resort
4. Provides helpful error messages

#### Wrapper Script Location
```
~/.local/bin/claude
```

This script survives corruption and system restarts, providing reliable Claude access.

### Manual Update Process

Since auto-updates are disabled, update Claude manually:

1. **Check current version:**
   ```bash
   claude --version
   ```

2. **Update (if no corruption):**
   ```bash
   npm update -g @anthropic-ai/claude-code
   ```

3. **If update fails with ENOTEMPTY:**
   - Follow cleanup steps above
   - Then reinstall fresh

### System Information

- **Node Version:** v24.1.0 (managed by nvm)
- **Shell:** zsh
- **Claude Installation Path:** `~/.nvm/versions/node/v24.1.0/lib/node_modules/@anthropic-ai/claude-code`
- **Wrapper Script:** `~/.local/bin/claude`
- **Auto-updates:** DISABLED via `DISABLE_AUTOUPDATER=1`

### Troubleshooting

#### Claude Command Not Found
1. Try the wrapper script directly: `~/.local/bin/claude --version`
2. Check if npm installation exists: `npm list -g | grep claude`
3. Verify nvm path: `ls ~/.nvm/versions/node/v24.1.0/bin/ | grep claude`

#### PATH Issues
The wrapper script handles most PATH issues automatically. If problems persist:
1. Ensure `~/.local/bin` is in PATH
2. Source shell profile: `source ~/.zshrc`
3. Check nvm initialization in `~/.zshrc`

---
*Last updated: 2025-08-22*
*Auto-updates disabled to prevent corruption*