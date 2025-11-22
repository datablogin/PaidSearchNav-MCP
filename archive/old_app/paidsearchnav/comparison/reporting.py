"""Report generation for audit comparisons."""

import json
from datetime import datetime
from typing import Dict

from jinja2 import Environment

from .models import ComparisonResult, TrendAnalysis
from .visualizations import ComparisonVisualizer


class ComparisonReporter:
    """Generate formatted reports from comparison results."""

    def __init__(self):
        """Initialize the reporter."""
        self.visualizer = ComparisonVisualizer()
        self.env = Environment()

    def generate_comparison_report(
        self,
        result: ComparisonResult,
        format: str = "markdown",
        include_visualizations: bool = True,
    ) -> str:
        """Generate a comprehensive comparison report."""
        if format == "markdown":
            return self._generate_markdown_report(result, include_visualizations)
        elif format == "html":
            return self._generate_html_report(result, include_visualizations)
        elif format == "json":
            return self._generate_json_report(result)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_markdown_report(
        self, result: ComparisonResult, include_visualizations: bool
    ) -> str:
        """Generate markdown formatted report."""
        template = """# Audit Comparison Report

## Executive Summary
**Period**: {{ baseline_date }} vs {{ comparison_date }}
**Generated**: {{ generated_at }}

### Key Metrics
- **Total Cost Savings**: ${{ "%.2f"|format(metrics.wasted_spend_reduction) }} ({{ "%.1f"|format(metrics.wasted_spend_reduction_pct) }}% improvement)
- **ROAS Change**: {{ "+%.1f"|format(metrics.roas_change_pct) if metrics.roas_change_pct > 0 else "%.1f"|format(metrics.roas_change_pct) }}%
- **Conversion Rate**: {{ "+%.1f"|format(metrics.conversion_rate_change_pct) if metrics.conversion_rate_change_pct > 0 else "%.1f"|format(metrics.conversion_rate_change_pct) }}%
- **CTR Improvement**: {{ "+%.1f"|format(metrics.ctr_improvement_pct) if metrics.ctr_improvement_pct > 0 else "%.1f"|format(metrics.ctr_improvement_pct) }}%

### Optimization Progress
- **Issues Resolved**: {{ metrics.issues_resolved }}
- **New Issues Found**: {{ metrics.new_issues_found }}
- **Keywords Analyzed**: {{ metrics.keywords_analyzed_change }} change

## Performance Analysis

### Cost Efficiency
- Total spend changed by {{ "%.1f"|format(metrics.total_spend_change_pct) }}% (${{ "%.2f"|format(metrics.total_spend_change) }})
- Wasted spend reduced by {{ "%.1f"|format(metrics.wasted_spend_reduction_pct) }}% (${{ "%.2f"|format(metrics.wasted_spend_reduction) }})
- Cost per conversion {{ "improved" if metrics.cost_per_conversion_change_pct < 0 else "increased" }} by {{ "%.1f"|format(abs(metrics.cost_per_conversion_change_pct)) }}%
- ROAS {{ "improved" if metrics.roas_change_pct > 0 else "declined" }} by {{ "%.1f"|format(abs(metrics.roas_change_pct)) }}%

### Traffic & Engagement
- Impressions: {{ "+%d"|format(metrics.impressions_change) if metrics.impressions_change > 0 else "%d"|format(metrics.impressions_change) }} ({{ "%.1f"|format(metrics.impressions_change_pct) }}%)
- Clicks: {{ "+%d"|format(metrics.clicks_change) if metrics.clicks_change > 0 else "%d"|format(metrics.clicks_change) }} ({{ "%.1f"|format(metrics.clicks_change_pct) }}%)
- CTR: {{ "+%.2f"|format(metrics.ctr_improvement) if metrics.ctr_improvement > 0 else "%.2f"|format(metrics.ctr_improvement) }} percentage points
- Quality Score Trend: {{ "+%.1f"|format(metrics.quality_score_trend) if metrics.quality_score_trend > 0 else "%.1f"|format(metrics.quality_score_trend) }}

### Conversions & Revenue
- Conversions: {{ "+%d"|format(metrics.conversions_change) if metrics.conversions_change > 0 else "%d"|format(metrics.conversions_change) }} ({{ "%.1f"|format(metrics.conversions_change_pct) }}%)
- Conversion Rate: {{ "+%.2f"|format(metrics.conversion_rate_change) if metrics.conversion_rate_change > 0 else "%.2f"|format(metrics.conversion_rate_change) }} percentage points

{% if metrics.is_statistically_significant %}
### Statistical Significance
{% for metric, is_significant in metrics.is_statistically_significant.items() %}
- {{ metric }}: {{ "✓ Statistically significant" if is_significant else "Not statistically significant" }}
{% endfor %}
{% endif %}

## Key Insights
{% for insight in insights %}
- {{ insight }}
{% endfor %}

{% if warnings %}
## ⚠️ Warnings
{% for warning in warnings %}
- {{ warning }}
{% endfor %}
{% endif %}

{% if recommendations_comparison %}
## Recommendations Analysis
- **Previous Audit**: {{ recommendations_comparison.baseline_count }} recommendations
- **Current Audit**: {{ recommendations_comparison.comparison_count }} recommendations
- **New Types**: {{ ", ".join(recommendations_comparison.new_recommendation_types) or "None" }}
- **Resolved Types**: {{ ", ".join(recommendations_comparison.resolved_recommendation_types) or "None" }}
{% endif %}

## Next Steps
1. Review and address any warnings identified above
2. Implement pending recommendations to further improve performance
3. Monitor newly identified issues closely
4. Schedule follow-up audit in 30 days to track progress

---
*Report generated by PaidSearchNav Audit Comparison Tool*
"""

        # Render template
        tmpl = self.env.from_string(template)
        report = tmpl.render(
            baseline_date=result.baseline_date.strftime("%Y-%m-%d"),
            comparison_date=result.comparison_date.strftime("%Y-%m-%d"),
            generated_at=result.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            metrics=result.metrics,
            insights=result.insights,
            warnings=result.warnings,
            recommendations_comparison=result.recommendations_comparison,
        )

        return report

    def _generate_html_report(
        self, result: ComparisonResult, include_visualizations: bool
    ) -> str:
        """Generate HTML formatted report with embedded visualizations."""
        # For now, convert markdown to basic HTML
        markdown_report = self._generate_markdown_report(result, False)

        html_template = """<!DOCTYPE html>
<html>
<head>
    <title>Audit Comparison Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1, h2, h3 {
            color: #333;
        }
        .metric-positive {
            color: #27ae60;
        }
        .metric-negative {
            color: #e74c3c;
        }
        .warning {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .insight {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        .chart-container {
            margin: 20px 0;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        {{ content }}
    </div>
</body>
</html>"""

        # Convert markdown to HTML (basic conversion)
        html_content = markdown_report.replace("\n", "<br>\n")
        html_content = html_content.replace("# ", "<h1>").replace("\n<br>", "</h1>\n")
        html_content = html_content.replace("## ", "<h2>").replace("\n<br>", "</h2>\n")
        html_content = html_content.replace("### ", "<h3>").replace("\n<br>", "</h3>\n")
        html_content = html_content.replace("- ", "<li>").replace("\n<br>", "</li>\n")

        tmpl = self.env.from_string(html_template)
        return tmpl.render(content=html_content)

    def _generate_json_report(self, result: ComparisonResult) -> str:
        """Generate JSON formatted report."""
        report_data = {
            "baseline_audit_id": result.baseline_audit_id,
            "comparison_audit_id": result.comparison_audit_id,
            "baseline_date": result.baseline_date.isoformat(),
            "comparison_date": result.comparison_date.isoformat(),
            "generated_at": result.generated_at.isoformat(),
            "metrics": {
                "cost_efficiency": {
                    "total_spend_change": result.metrics.total_spend_change,
                    "total_spend_change_pct": result.metrics.total_spend_change_pct,
                    "wasted_spend_reduction": result.metrics.wasted_spend_reduction,
                    "wasted_spend_reduction_pct": result.metrics.wasted_spend_reduction_pct,
                    "cost_per_conversion_change": result.metrics.cost_per_conversion_change,
                    "cost_per_conversion_change_pct": result.metrics.cost_per_conversion_change_pct,
                    "roas_change": result.metrics.roas_change,
                    "roas_change_pct": result.metrics.roas_change_pct,
                },
                "performance": {
                    "ctr_improvement": result.metrics.ctr_improvement,
                    "ctr_improvement_pct": result.metrics.ctr_improvement_pct,
                    "conversion_rate_change": result.metrics.conversion_rate_change,
                    "conversion_rate_change_pct": result.metrics.conversion_rate_change_pct,
                    "quality_score_trend": result.metrics.quality_score_trend,
                },
                "volume": {
                    "impressions_change": result.metrics.impressions_change,
                    "impressions_change_pct": result.metrics.impressions_change_pct,
                    "clicks_change": result.metrics.clicks_change,
                    "clicks_change_pct": result.metrics.clicks_change_pct,
                    "conversions_change": result.metrics.conversions_change,
                    "conversions_change_pct": result.metrics.conversions_change_pct,
                },
                "optimization": {
                    "issues_resolved": result.metrics.issues_resolved,
                    "new_issues_found": result.metrics.new_issues_found,
                    "keywords_analyzed_change": result.metrics.keywords_analyzed_change,
                    "negative_keywords_added": result.metrics.negative_keywords_added,
                    "match_type_optimizations": result.metrics.match_type_optimizations,
                },
                "statistical_significance": result.metrics.is_statistically_significant,
            },
            "insights": result.insights,
            "warnings": result.warnings,
            "recommendations_comparison": result.recommendations_comparison,
        }

        return json.dumps(report_data, indent=2)

    def generate_trend_report(
        self,
        trend_analyses: Dict[str, TrendAnalysis],
        customer_id: str,
        format: str = "markdown",
    ) -> str:
        """Generate a trend analysis report."""
        if format == "markdown":
            return self._generate_trend_markdown(trend_analyses, customer_id)
        elif format == "json":
            return self._generate_trend_json(trend_analyses)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_trend_markdown(
        self, trend_analyses: Dict[str, TrendAnalysis], customer_id: str
    ) -> str:
        """Generate markdown trend report."""
        template = """# Trend Analysis Report
**Customer**: {{ customer_id }}
**Generated**: {{ generated_at }}

## Summary
Analyzed {{ num_metrics }} metrics over the period {{ start_date }} to {{ end_date }}.

{% for metric_name, analysis in analyses.items() %}
## {{ metric_name }}

**Trend**: {{ analysis.trend_direction|capitalize }} (Strength: {{ "%.2f"|format(analysis.trend_strength) }})
**Data Points**: {{ analysis.data_points|length }}
**Anomalies Detected**: {{ analysis.anomalies_detected }}
{% if analysis.seasonality_detected %}
**Seasonality**: Detected
{% endif %}

### Insights
{% for insight in analysis.insights %}
- {{ insight }}
{% endfor %}

{% if analysis.forecast %}
### Forecast
Next {{ analysis.forecast|length }} periods projected {{ "increase" if analysis.forecast[-1].value > analysis.data_points[-1].value else "decrease" }} of {{ "%.1f"|format(((analysis.forecast[-1].value - analysis.data_points[-1].value) / analysis.data_points[-1].value) * 100) }}%
{% endif %}

---
{% endfor %}

## Recommendations
1. Focus on metrics showing declining trends
2. Investigate anomalies for root causes
3. Leverage seasonal patterns for budget planning
4. Monitor forecast accuracy and adjust strategies

*Report generated by PaidSearchNav Trend Analysis Tool*
"""

        if not trend_analyses:
            return "# Trend Analysis Report\n\nNo data available for analysis."

        # Get date range from first analysis
        first_analysis = next(iter(trend_analyses.values()))

        tmpl = self.env.from_string(template)
        return tmpl.render(
            customer_id=customer_id,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            num_metrics=len(trend_analyses),
            start_date=first_analysis.start_date.strftime("%Y-%m-%d"),
            end_date=first_analysis.end_date.strftime("%Y-%m-%d"),
            analyses=trend_analyses,
        )

    def _generate_trend_json(self, trend_analyses: Dict[str, TrendAnalysis]) -> str:
        """Generate JSON trend report."""
        report_data = {}

        for metric_name, analysis in trend_analyses.items():
            report_data[metric_name] = {
                "customer_id": analysis.customer_id,
                "metric_type": analysis.metric_type.value,
                "start_date": analysis.start_date.isoformat(),
                "end_date": analysis.end_date.isoformat(),
                "granularity": analysis.granularity.value,
                "trend_direction": analysis.trend_direction,
                "trend_strength": analysis.trend_strength,
                "seasonality_detected": analysis.seasonality_detected,
                "anomalies_detected": analysis.anomalies_detected,
                "data_points": [
                    {
                        "timestamp": dp.timestamp.isoformat(),
                        "value": dp.value,
                        "is_anomaly": dp.is_anomaly,
                        "anomaly_score": dp.anomaly_score,
                    }
                    for dp in analysis.data_points
                ],
                "forecast": [
                    {"timestamp": dp.timestamp.isoformat(), "value": dp.value}
                    for dp in (analysis.forecast or [])
                ],
                "insights": analysis.insights,
            }

        return json.dumps(report_data, indent=2)
