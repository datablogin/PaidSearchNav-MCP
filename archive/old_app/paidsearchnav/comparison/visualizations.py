"""Visualization components for audit comparisons and trends."""

import base64
import io
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure

from .models import ComparisonMetrics, TrendAnalysis

# Set style for professional looking charts
try:
    plt.style.use("seaborn-v0_8-darkgrid")
except OSError:
    plt.style.use("seaborn-darkgrid")  # Fallback for older versions
sns.set_palette("husl")


class ComparisonVisualizer:
    """Create visualizations for audit comparisons and trends."""

    def __init__(self, style: str = "professional"):
        """Initialize visualizer with style settings."""
        self.style = style
        self._setup_style()

    def _setup_style(self):
        """Setup matplotlib style settings."""
        if self.style == "professional":
            plt.rcParams.update(
                {
                    "figure.figsize": (10, 6),
                    "font.size": 10,
                    "axes.titlesize": 14,
                    "axes.labelsize": 12,
                    "xtick.labelsize": 10,
                    "ytick.labelsize": 10,
                    "legend.fontsize": 10,
                    "figure.dpi": 100,
                }
            )

    def create_trend_chart(
        self,
        trend_analysis: TrendAnalysis,
        title: Optional[str] = None,
        show_forecast: bool = True,
        show_anomalies: bool = True,
    ) -> str:
        """Create a line chart showing metric trend over time."""
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data
        timestamps = [dp.timestamp for dp in trend_analysis.data_points]
        values = [dp.value for dp in trend_analysis.data_points]

        # Plot actual values
        ax.plot(
            timestamps,
            values,
            marker="o",
            linewidth=2,
            markersize=6,
            label="Actual",
            color="#1f77b4",
        )

        # Plot forecast if available
        if show_forecast and trend_analysis.forecast:
            forecast_timestamps = [dp.timestamp for dp in trend_analysis.forecast]
            forecast_values = [dp.value for dp in trend_analysis.forecast]

            ax.plot(
                forecast_timestamps,
                forecast_values,
                marker="s",
                linewidth=2,
                markersize=6,
                linestyle="--",
                label="Forecast",
                color="#ff7f0e",
                alpha=0.7,
            )

        # Highlight anomalies
        if show_anomalies:
            anomaly_timestamps = [
                dp.timestamp for dp in trend_analysis.data_points if dp.is_anomaly
            ]
            anomaly_values = [
                dp.value for dp in trend_analysis.data_points if dp.is_anomaly
            ]

            if anomaly_timestamps:
                ax.scatter(
                    anomaly_timestamps,
                    anomaly_values,
                    color="red",
                    s=100,
                    zorder=5,
                    label="Anomalies",
                    edgecolors="darkred",
                    linewidth=2,
                )

        # Add trend line
        if len(values) > 1:
            z = np.polyfit(range(len(values)), values, 1)
            p = np.poly1d(z)
            ax.plot(
                timestamps,
                p(range(len(values))),
                "--",
                color="gray",
                alpha=0.5,
                label=f"Trend ({trend_analysis.trend_direction})",
            )

        # Formatting
        ax.set_xlabel("Date")
        ax.set_ylabel(self._format_metric_label(trend_analysis.metric_type))
        ax.set_title(
            title
            or f"{trend_analysis.metric_type.value} Trend Analysis - {trend_analysis.customer_id}"
        )

        # Format x-axis dates
        fig.autofmt_xdate()

        # Add grid
        ax.grid(True, alpha=0.3)

        # Add legend
        ax.legend(loc="best")

        # Add trend strength annotation
        ax.text(
            0.02,
            0.98,
            f"Trend Strength: {trend_analysis.trend_strength:.2f}",
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        # Convert to base64 string
        return self._fig_to_base64(fig)

    def create_comparison_bar_chart(
        self,
        metrics: ComparisonMetrics,
        metric_names: Optional[List[str]] = None,
        title: str = "Audit Metrics Comparison",
    ) -> str:
        """Create bar chart comparing key metrics between audits."""
        if metric_names is None:
            metric_names = [
                "CTR",
                "Conversion Rate",
                "CPC",
                "ROAS",
                "Wasted Spend",
            ]

        # Prepare data
        changes = {
            "CTR": metrics.ctr_improvement_pct,
            "Conversion Rate": metrics.conversion_rate_change_pct,
            "CPC": metrics.cost_per_conversion_change_pct,
            "ROAS": metrics.roas_change_pct,
            "Wasted Spend": -metrics.wasted_spend_reduction_pct,  # Negative is good
        }

        # Filter to requested metrics
        data = {k: v for k, v in changes.items() if k in metric_names}

        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bars
        metrics_list = list(data.keys())
        values_list = list(data.values())
        colors = ["green" if v > 0 else "red" for v in values_list]

        # Adjust colors for metrics where decrease is good
        for i, metric in enumerate(metrics_list):
            if metric in ["CPC", "Wasted Spend"] and values_list[i] < 0:
                colors[i] = "green"
            elif metric in ["CPC", "Wasted Spend"] and values_list[i] > 0:
                colors[i] = "red"

        bars = ax.bar(metrics_list, values_list, color=colors, alpha=0.7)

        # Add value labels on bars
        for bar, value in zip(bars, values_list):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height / 2,
                f"{value:+.1f}%",
                ha="center",
                va="center",
                fontweight="bold",
                color="white",
            )

        # Formatting
        ax.set_ylabel("Percentage Change (%)")
        ax.set_title(title)
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.grid(True, axis="y", alpha=0.3)

        # Add statistical significance markers
        if metrics.is_statistically_significant:
            for i, metric in enumerate(metrics_list):
                metric_key = metric.lower().replace(" ", "_")
                if metrics.is_statistically_significant.get(metric_key, False):
                    ax.text(
                        i,
                        values_list[i] + 2,
                        "*",
                        ha="center",
                        fontsize=16,
                        fontweight="bold",
                    )

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def create_waterfall_chart(
        self,
        baseline_spend: float,
        savings_breakdown: Dict[str, float],
        title: str = "Cost Savings Breakdown",
    ) -> str:
        """Create waterfall chart showing cost savings breakdown."""
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data
        categories = (
            ["Baseline Spend"] + list(savings_breakdown.keys()) + ["Final Spend"]
        )
        values = [baseline_spend]

        # Calculate cumulative effect
        cumulative = baseline_spend
        for saving in savings_breakdown.values():
            cumulative -= saving  # Savings are reductions
            values.append(cumulative)

        # Create the waterfall effect
        for i in range(len(categories) - 1):
            if i == 0:
                # Starting bar
                ax.bar(
                    i,
                    values[i],
                    color="#1f77b4",
                    alpha=0.7,
                    label="Starting value",
                )
            elif i == len(categories) - 2:
                # Ending bar
                ax.bar(i, values[i], color="#2ca02c", alpha=0.7, label="Final value")
            else:
                # Floating bars for changes
                bottom = values[i]
                height = values[i - 1] - values[i]
                ax.bar(
                    i,
                    height,
                    bottom=bottom,
                    color="#ff7f0e",
                    alpha=0.7,
                    label="Savings" if i == 1 else "",
                )

                # Add connector lines
                ax.plot([i - 1, i], [values[i - 1], values[i]], "k--", alpha=0.5)

        # Labels and formatting
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=45, ha="right")
        ax.set_ylabel("Spend ($)")
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)

        # Add value labels
        for i, (cat, val) in enumerate(zip(categories, values)):
            if i > 0 and i < len(categories) - 1:
                change = values[i - 1] - values[i]
                ax.text(
                    i,
                    values[i] + change / 2,
                    f"-${change:,.0f}",
                    ha="center",
                    va="center",
                    fontweight="bold",
                )

        # Add total savings annotation
        total_savings = baseline_spend - values[-1]
        ax.text(
            0.98,
            0.98,
            f"Total Savings: ${total_savings:,.0f} ({(total_savings / baseline_spend) * 100:.1f}%)",
            transform=ax.transAxes,
            ha="right",
            va="top",
            bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.5),
            fontweight="bold",
        )

        plt.legend()
        plt.tight_layout()
        return self._fig_to_base64(fig)

    def create_heatmap(
        self,
        data: Dict[str, Dict[str, float]],
        title: str = "Performance Heatmap",
        metric_label: str = "Value",
    ) -> str:
        """Create heatmap visualization for campaign/ad group performance."""
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(data)

        if df.empty:
            return self._create_empty_chart("No data available for heatmap")

        fig, ax = plt.subplots(figsize=(12, 8))

        # Create heatmap
        sns.heatmap(
            df,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn",
            center=0,
            cbar_kws={"label": metric_label},
            ax=ax,
        )

        ax.set_title(title)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    def create_sparklines(
        self, data_series: List[float], width: int = 100, height: int = 20
    ) -> str:
        """Create small inline sparkline charts."""
        fig, ax = plt.subplots(figsize=(width / 100, height / 100))

        # Remove all axes and labels
        ax.plot(data_series, linewidth=1)
        ax.axis("off")

        # Remove margins
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

        return self._fig_to_base64(fig, dpi=100)

    def create_progress_bars(
        self,
        implementation_data: Dict[str, float],
        title: str = "Recommendation Implementation Progress",
    ) -> str:
        """Create horizontal progress bars for implementation tracking."""
        fig, ax = plt.subplots(figsize=(10, 6))

        categories = list(implementation_data.keys())
        values = list(implementation_data.values())

        # Create horizontal bars
        y_positions = np.arange(len(categories))
        bars = ax.barh(y_positions, values, alpha=0.7)

        # Color code based on progress
        for bar, value in zip(bars, values):
            if value >= 80:
                bar.set_color("green")
            elif value >= 50:
                bar.set_color("orange")
            else:
                bar.set_color("red")

        # Add value labels
        for i, (bar, value) in enumerate(zip(bars, values)):
            ax.text(
                value + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.0f}%",
                va="center",
                fontweight="bold",
            )

        # Formatting
        ax.set_yticks(y_positions)
        ax.set_yticklabels(categories)
        ax.set_xlabel("Implementation Progress (%)")
        ax.set_title(title)
        ax.set_xlim(0, 105)
        ax.grid(True, axis="x", alpha=0.3)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def _format_metric_label(self, metric_type: Any) -> str:
        """Format metric type for display."""
        label_map = {
            "total_spend": "Total Spend ($)",
            "wasted_spend": "Wasted Spend ($)",
            "cost_per_conversion": "Cost per Conversion ($)",
            "roas": "ROAS",
            "ctr": "CTR (%)",
            "conversion_rate": "Conversion Rate (%)",
            "quality_score": "Quality Score",
            "impressions": "Impressions",
            "clicks": "Clicks",
            "conversions": "Conversions",
        }
        return label_map.get(str(metric_type.value), str(metric_type.value))

    def _fig_to_base64(self, fig: Figure, dpi: int = 100) -> str:
        """Convert matplotlib figure to base64 string."""
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close(fig)
        return f"data:image/png;base64,{image_base64}"

    def _create_empty_chart(self, message: str) -> str:
        """Create placeholder chart when no data is available."""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=14,
            color="gray",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)
        return self._fig_to_base64(fig)
