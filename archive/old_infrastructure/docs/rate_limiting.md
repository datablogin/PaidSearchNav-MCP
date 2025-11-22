# Rate Limiting for ID Lists

PaidSearchNav implements rate limiting for campaign and ad group ID lists to prevent potential DoS attacks through resource exhaustion.

## Overview

When querying data with large lists of campaign or ad group IDs, the system enforces limits to ensure API performance and stability. This prevents malicious or accidental requests from overwhelming the system.

## Configuration

### Default Limit

By default, a maximum of **1000 IDs per request** is allowed for any ID list parameter.

### Environment Variable

You can configure the maximum allowed IDs using the `PSN_MAX_IDS_PER_REQUEST` environment variable:

```bash
# Set maximum to 500 IDs per request
export PSN_MAX_IDS_PER_REQUEST=500
```

## Affected Methods

Rate limiting is applied to the following data provider methods:

- `get_search_terms()` - `campaigns` and `ad_groups` parameters
- `get_keywords()` - `campaigns` and `ad_groups` parameters

## Error Handling

When a request exceeds the configured limit, a `RateLimitError` is raised with a clear message:

```python
from paidsearchnav.security.rate_limiting import RateLimitError

try:
    # This will fail if campaigns list has more than max allowed IDs
    search_terms = await provider.get_search_terms(
        customer_id="123",
        start_date=start_date,
        end_date=end_date,
        campaigns=large_campaign_list,  # > 1000 items
    )
except RateLimitError as e:
    print(f"Error: {e}")
    # Output: "Error: Too many campaigns provided: 1500 exceeds maximum of 1000. 
    #          Please use pagination or reduce the number of campaigns in your request."
```

## Pagination Support

For legitimate use cases requiring large datasets, use the built-in pagination helpers:

```python
from paidsearchnav.security.rate_limiting import paginate_id_list

# Split large campaign list into pages
campaign_pages = paginate_id_list(large_campaign_list, page_size=500)

# Process each page separately
all_results = []
for campaign_page in campaign_pages:
    results = await provider.get_search_terms(
        customer_id="123",
        start_date=start_date,
        end_date=end_date,
        campaigns=campaign_page,
    )
    all_results.extend(results)
```

## Manual Validation

You can also manually validate ID lists before making requests:

```python
from paidsearchnav.security.rate_limiting import validate_id_list_size

# Validate a single list
try:
    validated_campaigns = validate_id_list_size(
        campaigns, 
        "campaigns",
        max_size=500  # Custom limit
    )
except RateLimitError:
    # Handle the error
    pass

# Validate multiple lists at once
from paidsearchnav.security.rate_limiting import validate_multiple_id_lists

validated = validate_multiple_id_lists(
    campaigns=campaign_list,
    ad_groups=ad_group_list,
)
```

## Best Practices

1. **Keep ID lists reasonable**: Try to keep your ID lists under 100 items for optimal performance
2. **Use filters wisely**: Instead of listing many IDs, consider using date ranges or other filters
3. **Implement pagination**: For large datasets, implement pagination in your application logic
4. **Cache results**: Cache results when querying the same IDs repeatedly
5. **Monitor usage**: Log and monitor ID list sizes to identify potential optimization opportunities

## Security Considerations

Rate limiting helps prevent:
- Resource exhaustion attacks
- Memory overflow from extremely large queries
- API rate limit exhaustion
- Database performance degradation

Always validate user input and implement appropriate access controls in addition to rate limiting.