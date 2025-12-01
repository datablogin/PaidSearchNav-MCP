# TestMinimal Skill

## Purpose
Minimal test skill to validate MCP server integration without context window overhead.

## What It Does
- Fetches 500 keywords via MCP server
- Reports basic statistics
- Tests pagination metadata
- Minimal analysis (just top 5 by cost)

## Usage

**In Claude Desktop:**
```
Test MCP connection for customer ID 5777461198
from 2025-07-01 to 2025-10-31
```

## Expected Result
Should complete in <10 seconds with a simple report showing:
- Number of keywords fetched
- Pagination status
- Top 5 keywords

## Why This Exists
This skill has a ~25 line prompt (vs 260 lines for full skills) to test if context window exhaustion is the issue with larger skills.

If this works but full skills fail → problem is prompt verbosity.
If this also fails → problem is elsewhere (data size, MCP config, etc).
