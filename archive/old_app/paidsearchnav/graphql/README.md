# GraphQL API Documentation

## Overview

The PaidSearchNav GraphQL API provides a flexible and efficient way to query and manipulate data. Built with Strawberry GraphQL, it offers:

- **Type Safety**: Strongly typed schema with automatic validation
- **Efficient Data Fetching**: Request only the data you need
- **DataLoader Integration**: Automatic N+1 query prevention
- **Real-time Updates**: Subscription support for live data
- **Security**: Built-in depth limiting and query complexity analysis

## Endpoints

- **GraphQL Endpoint**: `/api/v1/graphql`
- **GraphiQL IDE**: `/api/v1/graphql` (development only)
- **WebSocket**: `/api/v1/graphql/ws` (for subscriptions)

## Authentication

The GraphQL API uses the same JWT authentication as the REST API. Include your token in the Authorization header:

```http
Authorization: Bearer <your-jwt-token>
```

## Schema Overview

### Queries

```graphql
type Query {
  # Get a single customer
  customer(id: ID!): Customer
  
  # List customers with optional filtering
  customers(filter: CustomerFilter): [Customer!]!
  
  # Get a single audit
  audit(id: ID!): Audit
  
  # List audits for a customer
  audits(customerId: ID!, limit: Int = 10): [Audit!]!
  
  # Get analysis results for an audit
  analysisResults(
    auditId: ID!
    analyzers: [AnalyzerType!]
  ): [AnalysisResult!]!
  
  # Get recommendations for a customer
  recommendations(
    customerId: ID!
    priority: Priority
    dateRange: DateRange
  ): [Recommendation!]!
}
```

### Mutations

```graphql
type Mutation {
  # Trigger a new audit
  triggerAudit(input: TriggerAuditInput!): Audit!
  
  # Schedule an audit for future execution
  scheduleAudit(input: ScheduleAuditInput!): ScheduledJob!
  
  # Cancel a running audit
  cancelAudit(auditId: ID!): Audit!
}
```

### Subscriptions

```graphql
type Subscription {
  # Subscribe to real-time audit progress
  auditProgress(auditId: ID!): AuditProgress!
}
```

## Example Queries

### Get Customer with Latest Audit

```graphql
query GetCustomerDetails($customerId: ID!) {
  customer(id: $customerId) {
    id
    name
    googleAdsAccountId
    isActive
    latestAudit {
      id
      status
      completedAt
      totalAnalyzers
      completedAnalyzers
    }
  }
}
```

### Get Audit with Analysis Results

```graphql
query GetAuditDetails($auditId: ID!) {
  audit(id: $auditId) {
    id
    status
    createdAt
    customer {
      id
      name
    }
    analysisResults {
      id
      analyzerType
      status
      score
      impactLevel
      issuesFound
      potentialSavings
    }
    recommendations {
      id
      title
      priority
      estimatedCostSavings
    }
  }
}
```

### List High-Priority Recommendations

```graphql
query GetHighPriorityRecommendations($customerId: ID!) {
  recommendations(
    customerId: $customerId
    priority: HIGH
  ) {
    id
    title
    description
    priority
    estimatedImpact
    estimatedCostSavings
    actionItems
    audit {
      id
      completedAt
    }
  }
}
```

## Example Mutations

### Trigger an Audit

```graphql
mutation TriggerNewAudit($customerId: ID!) {
  triggerAudit(input: {
    customerId: $customerId
    analyzers: [
      KEYWORD_PERFORMANCE,
      AD_COPY_EFFECTIVENESS,
      BID_STRATEGY
    ]
    forceRefresh: true
  }) {
    id
    status
    totalAnalyzers
  }
}
```

### Schedule a Recurring Audit

```graphql
mutation ScheduleWeeklyAudit($customerId: ID!) {
  scheduleAudit(input: {
    customerId: $customerId
    scheduleAt: "2024-01-15T09:00:00Z"
    recurrence: "0 9 * * MON"  # Every Monday at 9 AM
    analyzers: [KEYWORD_PERFORMANCE]
  }) {
    id
    status
    scheduledAt
    recurrence
    nextRun
  }
}
```

## Example Subscription

### Monitor Audit Progress

```graphql
subscription MonitorAudit($auditId: ID!) {
  auditProgress(auditId: $auditId) {
    auditId
    status
    currentAnalyzer
    progressPercentage
    message
    completedAnalyzers
    totalAnalyzers
  }
}
```

## DataLoader Usage

The GraphQL API automatically uses DataLoaders to batch and cache requests. This prevents N+1 query problems when fetching related data:

```graphql
# This query efficiently loads all data with minimal database queries
query GetCustomersWithAudits {
  customers {
    id
    name
    audits(limit: 5) {  # DataLoader batches all audit queries
      id
      status
      analysisResults {  # DataLoader batches all result queries
        analyzerType
        score
      }
    }
  }
}
```

## Security Features

### Query Depth Limiting

Queries are limited to a maximum depth of 10 levels to prevent abuse:

```graphql
# This would be rejected (too deep)
query TooDeep {
  customer {
    audits {
      analysisResults {
        audit {
          customer {
            audits {
              analysisResults {
                audit {
                  customer {
                    audits {  # Depth > 10
                      ...
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Query Complexity Analysis

Queries are analyzed for complexity to prevent resource-intensive operations:

- Scalar fields: 1 point
- Object fields: 5 points
- List fields: 10+ points (multiplied by limit)

Maximum complexity: 1000 points

### Field-Level Permissions

Some fields may require specific permissions:

- Financial data requires `billing:read` permission
- Audit mutations require `audit:write` permission
- Customer management requires `customer:admin` permission

## Error Handling

GraphQL errors follow a consistent format:

```json
{
  "errors": [
    {
      "message": "Customer not found",
      "path": ["customer"],
      "extensions": {
        "code": "NOT_FOUND",
        "customerId": "123"
      }
    }
  ],
  "data": {
    "customer": null
  }
}
```

## Best Practices

1. **Request Only What You Need**: Take advantage of GraphQL's selective field querying
2. **Use Fragments**: Define reusable field selections for common patterns
3. **Batch Operations**: Use DataLoader-enabled fields for efficient data loading
4. **Handle Errors**: Check both the `errors` array and null values in responses
5. **Use Variables**: Pass dynamic values as variables rather than string interpolation
6. **Monitor Performance**: Use the included metrics to track query performance

## Performance Monitoring

The GraphQL API includes built-in performance monitoring:

- Query execution time
- Resolver performance metrics
- DataLoader statistics
- Cache hit rates

Access metrics at `/metrics` (requires admin permissions).