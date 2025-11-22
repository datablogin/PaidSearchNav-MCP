# API Version Migration Guide

This guide helps you migrate between different versions of the PaidSearchNav API.

## Table of Contents

- [Version Overview](#version-overview)
- [Version Negotiation](#version-negotiation)
- [Migration Guides](#migration-guides)
  - [Migrating from v1.0 to v1.1](#migrating-from-v10-to-v11)
  - [Migrating from v1.1 to v2.0](#migrating-from-v11-to-v20)
- [Deprecation Policy](#deprecation-policy)
- [Best Practices](#best-practices)

## Version Overview

| Version | Status | Released | Description |
|---------|--------|----------|-------------|
| 1.0 | Stable | 2024-01-01 | Initial release with core functionality |
| 1.1 | Beta | 2025-02-01 | Added bulk operations and enhanced filtering |
| 2.0 | Beta | 2025-06-01 | Major redesign with GraphQL support |

## Version Negotiation

The PaidSearchNav API supports multiple methods for specifying the API version:

### 1. URL-based Versioning (Recommended)

Include the version in the URL path:

```bash
GET /api/v1/audits
GET /api/v2/audits
```

### 2. Header-based Versioning

Use the `Accept` header with vendor-specific media type:

```bash
curl -H "Accept: application/vnd.psn.v1+json" https://api.paidsearchnav.com/api/audits
```

### 3. Custom Header

Use the `X-API-Version` header:

```bash
curl -H "X-API-Version: 1.1" https://api.paidsearchnav.com/api/audits
```

### 4. Query Parameter

Add version as a query parameter:

```bash
GET /api/audits?version=1.0
```

## Migration Guides

### Migrating from v1.0 to v1.1

Version 1.1 is backward compatible with v1.0, adding new features without breaking changes.

#### New Features in v1.1

1. **Bulk Operations**
   - New endpoints: `/api/v1/audits/bulk`, `/api/v1/customers/bulk`
   - Process multiple items in a single request
   - Example:
     ```json
     POST /api/v1/audits/bulk
     {
       "items": [
         {"customer_id": "123", "analysis_type": "keyword"},
         {"customer_id": "456", "analysis_type": "negative"}
       ]
     }
     ```

2. **Enhanced Filtering**
   - Additional query parameters for list endpoints
   - Support for complex filters and sorting

3. **WebSocket Improvements**
   - New event types for real-time updates
   - Improved connection stability

#### Code Changes

No breaking changes. Your v1.0 code will continue to work with v1.1.

### Migrating from v1.1 to v2.0

Version 2.0 introduces breaking changes and requires code updates.

#### Breaking Changes

1. **Field Naming Convention**
   - Changed from snake_case to camelCase
   - Example: `customer_id` → `customerId`
   
   **Before (v1.1):**
   ```json
   {
     "customer_id": "123-456-7890",
     "analysis_type": "keyword",
     "start_date": "2024-01-01"
   }
   ```
   
   **After (v2.0):**
   ```json
   {
     "customerId": "123-456-7890",
     "analysisType": "keyword",
     "startDate": "2024-01-01"
   }
   ```

2. **Authentication Flow**
   - New OAuth 2.0 flow replaces JWT tokens
   - Refresh tokens now required
   - See [Authentication Guide](./authentication.md) for details

3. **Response Format**
   - Standardized error responses
   - Consistent pagination structure
   - New metadata fields

4. **Removed Endpoints**
   - `/api/v1/legacy/*` endpoints removed
   - Use new alternatives listed below

#### Endpoint Mapping

| v1.1 Endpoint | v2.0 Endpoint | Notes |
|---------------|---------------|-------|
| GET /api/v1/audits | GET /api/v2/audits | Field names changed |
| POST /api/v1/audits | POST /api/v2/audits | Request body format updated |
| GET /api/v1/legacy/endpoint | GET /api/v2/new-endpoint | Complete redesign |

#### Migration Steps

1. **Update Authentication**
   ```python
   # v1.1
   headers = {"Authorization": f"Bearer {jwt_token}"}
   
   # v2.0
   headers = {"Authorization": f"Bearer {oauth_token}"}
   ```

2. **Update Field Names**
   ```python
   # v1.1
   data = {
       "customer_id": "123",
       "analysis_type": "keyword"
   }
   
   # v2.0
   data = {
       "customerId": "123",
       "analysisType": "keyword"
   }
   ```

3. **Handle New Response Format**
   ```python
   # v1.1
   results = response.json()["results"]
   
   # v2.0
   results = response.json()["data"]["results"]
   ```

## Deprecation Policy

- **Notice Period**: 6 months advance notice before deprecation
- **Sunset Period**: 12 months from deprecation to removal
- **Communication**: Via API headers, documentation, and email notifications

### Deprecation Headers

When using a deprecated version, responses include:

```
Sunset: Sat, 31 Dec 2025 23:59:59 GMT
Deprecation: true
Link: </docs/api/migration>; rel="deprecation"
```

## Best Practices

1. **Always Specify Version**
   - Don't rely on default version behavior
   - Explicitly specify version in production

2. **Monitor Deprecation Notices**
   - Check response headers for deprecation warnings
   - Subscribe to API updates

3. **Test Before Migration**
   - Use version-specific documentation
   - Test in staging environment first

4. **Gradual Migration**
   - Update authentication first
   - Migrate endpoints incrementally
   - Monitor for errors

5. **Use Transformation Layer**
   - Create adapter layer for version differences
   - Simplifies future migrations

### Example Migration Adapter

```python
class ApiAdapter:
    def __init__(self, version="1.0"):
        self.version = version
    
    def transform_request(self, data):
        if self.version == "2.0":
            # Transform snake_case to camelCase
            return {self.to_camel_case(k): v for k, v in data.items()}
        return data
    
    def transform_response(self, data):
        if self.version == "2.0":
            # Extract data from new format
            return data.get("data", data)
        return data
    
    @staticmethod
    def to_camel_case(snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
```

## Support

For migration assistance:
- GitHub Issues: https://github.com/datablogin/PaidSearchNav/issues
- Email: api-support@paidsearchnav.com
- Documentation: https://docs.paidsearchnav.com/api