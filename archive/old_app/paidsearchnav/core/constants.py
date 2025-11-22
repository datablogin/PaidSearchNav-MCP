"""Constants for PaidSearchNav application."""

# Validation limits for cost and revenue in micros
# Max reasonable cost: $10M = 10,000,000,000,000 micros
MAX_COST_MICROS = 10_000_000_000_000

# Max reasonable revenue: $100M = 100,000,000,000,000 micros
MAX_REVENUE_MICROS = 100_000_000_000_000

# Conversion factor from micros to currency units
MICROS_TO_CURRENCY = 1_000_000

# Default CPA fallback value when no historical data available
DEFAULT_CPA_FALLBACK = 100.0
