"""Base model with common fields and configuration."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, field_serializer


def utc_now() -> datetime:
    """Get current UTC datetime (Python 3.12 compatible)."""
    return datetime.now(timezone.utc)


class BasePSNModel(PydanticBaseModel):
    """Base model for all PaidSearchNav models."""

    created_at: datetime = Field(
        default_factory=utc_now, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update timestamp"
    )

    model_config = {
        # Use enum values instead of names
        "use_enum_values": True,
        # Validate on assignment
        "validate_assignment": True,
        # Allow population by field name
        "populate_by_name": True,
    }

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO format."""
        return dt.isoformat()

    def model_dump_json(self, **kwargs) -> str:
        """Override to ensure datetime serialization."""
        # Remove 'mode' if present as it's not a valid parameter
        kwargs.pop("mode", None)
        return super().model_dump_json(**kwargs)


class BaseModel(BasePSNModel):
    """Alias for BasePSNModel for backward compatibility."""

    id: str | None = Field(None, description="Unique identifier")


class MetricPeriod(str, Enum):
    """Enum for metric time period types."""

    REPORTING_PERIOD = "reporting_period"
    MONTHLY_PROJECTION = "monthly_projection"
    MONTHLY_CURRENT = "monthly_current"
    DAILY_AVERAGE = "daily_average"
    LIFETIME_TOTAL = "lifetime_total"


class MetricWithContext(BasePSNModel):
    """A metric value with time period context and metadata."""

    value: Any = Field(..., description="The metric value")
    period: MetricPeriod = Field(..., description="Time period this metric represents")
    unit: str = Field(
        ..., description="Unit of measurement (e.g., USD, count, percentage)"
    )
    description: str = Field(
        ..., description="Human-readable description of the metric"
    )
    calculation_method: Optional[str] = Field(
        None, description="Optional description of how the metric was calculated"
    )

    def model_post_init(self, __context) -> None:
        """Post-init validation after all fields are set."""
        # Validate savings and revenue values should be non-negative
        if isinstance(self.value, (int, float)) and (
            "saving" in self.description.lower()
            or "revenue" in self.description.lower()
        ):
            if self.value < 0:
                raise ValueError(
                    f"Savings and revenue metrics must be non-negative, got {self.value}"
                )

        # Validate percentage values are in reasonable range
        if self.unit == "percentage" and isinstance(self.value, (int, float)):
            if self.value < 0 or self.value > 100:
                raise ValueError(
                    f"Percentage values must be between 0 and 100, got {self.value}"
                )

        # Validate count values are non-negative integers
        if self.unit == "count" and isinstance(self.value, (int, float)):
            if self.value < 0:
                raise ValueError(
                    f"Count metrics must be non-negative, got {self.value}"
                )

    def format_value(self, locale: str = "en_US", currency: str = "USD") -> str:
        """Format the metric value according to locale and currency preferences.

        Args:
            locale: Locale string (e.g., 'en_US', 'en_GB', 'de_DE')
            currency: Currency code for USD metrics (e.g., 'USD', 'EUR', 'GBP')

        Returns:
            Formatted string representation of the value
        """
        if not isinstance(self.value, (int, float)):
            return str(self.value)

        # Format currency values
        if self.unit == "USD":
            if locale.startswith("en_US"):
                return f"${self.value:,.2f}"
            elif locale.startswith("en_GB"):
                symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, "$")
                return f"{symbol}{self.value:,.2f}"
            elif locale.startswith("de"):
                symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, "$")
                return (
                    f"{self.value:,.2f} {symbol}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )
            else:
                return f"${self.value:,.2f}"

        # Format percentage values
        elif self.unit == "percentage":
            if locale.startswith("de"):
                return f"{self.value:.1f}%".replace(".", ",")
            else:
                return f"{self.value:.1f}%"

        # Format count values
        elif self.unit == "count":
            if locale.startswith("de"):
                return f"{int(self.value):,}".replace(",", ".")
            else:
                return f"{int(self.value):,}"

        # Default formatting for other units
        else:
            if isinstance(self.value, float):
                if locale.startswith("de"):
                    return f"{self.value:.2f}".replace(".", ",")
                else:
                    return f"{self.value:.2f}"
            else:
                return str(self.value)

    def to_display_dict(
        self, locale: str = "en_US", currency: str = "USD"
    ) -> Dict[str, Any]:
        """Convert to a dictionary optimized for display with formatted values.

        Args:
            locale: Locale for formatting
            currency: Currency for financial values

        Returns:
            Dictionary with formatted display information
        """
        return {
            "raw_value": self.value,
            "formatted_value": self.format_value(locale, currency),
            "unit": self.unit,
            "period": self.period,
            "period_label": self.period.replace("_", " ").title(),
            "description": self.description,
            "calculation_method": self.calculation_method,
        }


class EnhancedKeyMetrics(BasePSNModel):
    """Enhanced key metrics format with time period context."""

    reporting_period: str = Field(
        ...,
        description="Human-readable reporting period (e.g., '2025-08-24 to 2025-08-31 (7 days)')",
    )
    metrics: Dict[str, MetricWithContext] = Field(
        default_factory=dict,
        description="Dictionary of metric names to MetricWithContext objects",
    )

    def get_metrics_by_period(
        self, period: MetricPeriod
    ) -> Dict[str, MetricWithContext]:
        """Filter metrics by their time period type.

        Args:
            period: The time period type to filter by

        Returns:
            Dictionary of metric names to MetricWithContext objects for the specified period
        """
        return {
            name: metric
            for name, metric in self.metrics.items()
            if metric.period == period
        }

    def get_financial_metrics(self) -> Dict[str, MetricWithContext]:
        """Get all metrics with USD unit (financial metrics).

        Returns:
            Dictionary of financial metrics
        """
        return {
            name: metric
            for name, metric in self.metrics.items()
            if metric.unit == "USD"
        }

    def get_summary_for_dashboard(self) -> Dict[str, Any]:
        """Generate a summary dictionary optimized for dashboard views.

        Returns:
            Simplified metrics dictionary with key values for dashboards
        """
        summary = {
            "reporting_period": self.reporting_period,
            "financial_summary": {},
            "performance_summary": {},
            "operational_summary": {},
        }

        for name, metric in self.metrics.items():
            value = metric.value

            # Aggregate financial metrics
            if metric.unit == "USD":
                summary["financial_summary"][name] = {
                    "value": value,
                    "period": metric.period,
                    "description": metric.description,
                }

            # Aggregate performance metrics (percentages and rates)
            elif metric.unit in ["percentage", "rate"]:
                summary["performance_summary"][name] = {
                    "value": value,
                    "unit": metric.unit,
                    "description": metric.description,
                }

            # Aggregate operational metrics (counts)
            elif metric.unit == "count":
                summary["operational_summary"][name] = {
                    "value": value,
                    "description": metric.description,
                }

        return summary

    @classmethod
    def aggregate_multiple_metrics(
        cls,
        metrics_list: List["EnhancedKeyMetrics"],
        aggregation_title: str = "Combined Analysis",
    ) -> "EnhancedKeyMetrics":
        """Aggregate metrics from multiple EnhancedKeyMetrics instances.

        Args:
            metrics_list: List of EnhancedKeyMetrics to aggregate
            aggregation_title: Title for the aggregated metrics

        Returns:
            New EnhancedKeyMetrics with aggregated values
        """
        if not metrics_list:
            return cls(reporting_period="No data", metrics={})

        # Combine reporting periods
        periods = [m.reporting_period for m in metrics_list]
        combined_period = f"{aggregation_title} ({len(metrics_list)} analyses)"

        # Aggregate metrics by name and type
        aggregated_metrics = {}

        for metrics_instance in metrics_list:
            for name, metric in metrics_instance.metrics.items():
                if name not in aggregated_metrics:
                    # Initialize aggregation for this metric
                    aggregated_metrics[name] = {
                        "values": [],
                        "unit": metric.unit,
                        "period": metric.period,
                        "description": metric.description,
                        "calculation_method": f"Aggregated from {len(metrics_list)} analyses",
                    }

                aggregated_metrics[name]["values"].append(metric.value)

        # Calculate aggregated values
        final_metrics = {}
        for name, agg_data in aggregated_metrics.items():
            values = agg_data["values"]

            # Handle different aggregation strategies based on unit type
            if agg_data["unit"] == "USD":
                # Sum financial values
                aggregated_value = sum(v for v in values if isinstance(v, (int, float)))
            elif agg_data["unit"] == "count":
                # Sum count values
                aggregated_value = sum(v for v in values if isinstance(v, (int, float)))
            elif agg_data["unit"] == "percentage":
                # Average percentage values
                numeric_values = [v for v in values if isinstance(v, (int, float))]
                aggregated_value = (
                    sum(numeric_values) / len(numeric_values) if numeric_values else 0
                )
            else:
                # For other types, take the first non-null value or use first value
                aggregated_value = next(
                    (v for v in values if v is not None), values[0] if values else None
                )

            final_metrics[name] = MetricWithContext(
                value=aggregated_value,
                period=agg_data["period"],
                unit=agg_data["unit"],
                description=f"{agg_data['description']} (aggregated)",
                calculation_method=agg_data["calculation_method"],
            )

        return cls(reporting_period=combined_period, metrics=final_metrics)
