# BigQuery Hybrid Pipeline Documentation

This directory contains comprehensive documentation for PaidSearchNav's BigQuery hybrid pipeline functionality, which provides enterprise-grade cost monitoring, real-time analytics, and automated export capabilities.

## 📖 Documentation Index

### User Documentation
- **[User Guide](user-guide.md)** - Complete guide for end users
- **[API Reference](api-reference.md)** - API endpoints with examples
- **[Cost Monitoring Guide](cost-monitoring.md)** - Cost management and budgets
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

### Developer Documentation
- **[Architecture Overview](architecture.md)** - System design and components
- **[Configuration Reference](configuration.md)** - Environment variables and settings
- **[Extension Guide](extension-guide.md)** - Adding new features and formats
- **[Performance Tuning](performance-tuning.md)** - Optimization recommendations

### Operational Documentation
- **[Deployment Guide](deployment.md)** - Setup and installation
- **[Monitoring Setup](monitoring-setup.md)** - Observability configuration
- **[Disaster Recovery](disaster-recovery.md)** - Backup and recovery procedures
- **[Cost Optimization](cost-optimization.md)** - Strategies for reducing BigQuery costs

## 🚀 Quick Start

1. **Prerequisites**: Ensure you have premium tier access and Google Cloud credentials
2. **Configuration**: Set up environment variables (see [Configuration Guide](configuration.md))
3. **Authentication**: Configure Google Cloud service account (see [Deployment Guide](deployment.md))
4. **Usage**: Start with the [User Guide](user-guide.md) for basic operations

## 🎯 Key Features

### Real-time Cost Monitoring
- Sub-5-minute cost tracking
- Budget enforcement with automatic throttling
- Multi-threshold alerting (50%, 80%, 95%)
- Emergency circuit breaker protection

### Advanced Analytics
- Anomaly detection for unusual usage patterns
- ROI analysis comparing BigQuery vs CSV operations
- Comprehensive cost breakdowns and trends
- Automated optimization recommendations

### Enterprise Security
- Role-based access controls
- Customer data isolation
- Admin-only budget configuration
- Comprehensive audit logging

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Layer    │    │  Cost Monitor    │    │  BigQuery       │
│                 │    │                  │    │  Service        │
│ • Authentication│───▶│ • Real-time      │───▶│                 │
│ • Rate Limiting │    │   tracking       │    │ • Analytics     │
│ • Validation    │    │ • Budget         │    │ • Data Export   │
│                 │    │   enforcement    │    │ • Query Engine  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Alert Manager   │
                       │                  │
                       │ • Notifications  │
                       │ • Rate Limiting  │
                       │ • Escalation     │
                       └──────────────────┘
```

## 🔧 Technology Stack

- **Backend**: FastAPI with async/await
- **Database**: BigQuery for analytics, PostgreSQL for metadata
- **Authentication**: Google Cloud IAM + JWT
- **Monitoring**: Prometheus metrics, structured logging
- **Cost Tracking**: BigQuery INFORMATION_SCHEMA integration

## 📊 Customer Tiers

| Feature | Standard | Premium | Enterprise |
|---------|----------|---------|------------|
| Daily Limit | $10 | $50 | $200 |
| Monthly Limit | $300 | $1,500 | $6,000 |
| Real-time Monitoring | ❌ | ✅ | ✅ |
| Advanced Analytics | ❌ | ✅ | ✅ |
| Custom Alerts | ❌ | ✅ | ✅ |
| ML Predictions | ❌ | ❌ | ✅ |

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/datablogin/PaidSearchNav/issues)
- **Documentation**: This directory contains comprehensive guides
- **Emergency**: Check [Troubleshooting Guide](troubleshooting.md) first

---

*Documentation for the latest version - see [releases](https://github.com/datablogin/PaidSearchNav/releases) for version information*