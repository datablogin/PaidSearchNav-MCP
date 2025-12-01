# Minimal Keyword Fetch Test

You are testing the PaidSearchNav MCP server integration.

## Task
1. Call `get_keywords(customer_id, start_date, end_date, limit=500)`
2. Report:
   - Total keywords received
   - Whether pagination is available (`has_more` in response)
   - Top 5 keywords by cost (keyword text and cost only)

## Output Format
```
✅ MCP Test Results
- Records fetched: [count]
- Pagination available: [yes/no]
- Has more data: [true/false if pagination exists]

Top 5 Keywords by Cost:
1. [keyword] - $[cost]
2. [keyword] - $[cost]
...
```

Keep response concise. This is a connectivity test only.
