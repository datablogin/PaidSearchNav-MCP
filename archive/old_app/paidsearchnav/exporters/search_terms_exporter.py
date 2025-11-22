"""Exporter for search terms analysis results."""

import csv
import io
import json
from typing import Any

import pandas as pd

from paidsearchnav.core.interfaces import Exporter
from paidsearchnav.core.models import SearchTerm, SearchTermAnalysisResult


class SearchTermsExporter(Exporter):
    """Export search terms analysis results to various formats."""

    def get_supported_formats(self) -> list[str]:
        """Get list of supported export formats."""
        return ["csv", "xlsx", "json"]

    def export(
        self,
        data: SearchTermAnalysisResult,
        filename: str,
        format: str = "csv",
        **kwargs: Any,
    ) -> bytes:
        """Export analysis results to specified format."""
        if format == "csv":
            return self._export_csv(data, **kwargs)
        elif format == "xlsx":
            return self._export_xlsx(data, **kwargs)
        elif format == "json":
            return self._export_json(data, **kwargs)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_csv(self, data: SearchTermAnalysisResult, **kwargs) -> bytes:
        """Export to CSV format."""
        output = io.StringIO()

        # Write summary section
        writer = csv.writer(output)
        writer.writerow(["Search Terms Analysis Summary"])
        writer.writerow([])
        writer.writerow(["Analysis Date:", data.created_at.isoformat()])
        writer.writerow(
            ["Date Range:", f"{data.start_date.date()} to {data.end_date.date()}"]
        )
        writer.writerow(["Total Search Terms:", data.total_search_terms])
        writer.writerow(["Total Cost:", f"${data.total_cost:,.2f}"])
        writer.writerow(["Total Conversions:", f"{data.total_conversions:,.2f}"])
        writer.writerow(["Overall CPA:", f"${data.overall_cpa:,.2f}"])
        writer.writerow([])

        # Write classification summary
        writer.writerow(["Classification Summary"])
        writer.writerow(["Category", "Count"])
        writer.writerow(["Add Candidates", len(data.add_candidates)])
        writer.writerow(["Negative Candidates", len(data.negative_candidates)])
        writer.writerow(["Already Covered", len(data.already_covered)])
        writer.writerow(["Review Needed", len(data.review_needed)])
        writer.writerow([])

        # Write detailed search terms
        if kwargs.get("include_details", True):
            # Add Candidates section
            if data.add_candidates:
                writer.writerow(["Add Candidates - High Performing Search Terms"])
                self._write_search_terms_csv(writer, data.add_candidates)
                writer.writerow([])

            # Negative Candidates section
            if data.negative_candidates:
                writer.writerow(["Negative Candidates - Poor Performing Search Terms"])
                self._write_search_terms_csv(writer, data.negative_candidates)
                writer.writerow([])

            # Review Needed section
            if data.review_needed and kwargs.get("include_review", False):
                writer.writerow(["Review Needed - Requires Manual Review"])
                self._write_search_terms_csv(writer, data.review_needed)
                writer.writerow([])

        # Write recommendations
        if data.recommendations:
            writer.writerow(["Recommendations"])
            for i, rec in enumerate(data.recommendations, 1):
                writer.writerow([f"{i}. [{rec.priority}] {rec.description}"])

        # Get string value and encode to bytes
        csv_content = output.getvalue()
        return csv_content.encode("utf-8-sig")  # UTF-8 with BOM for Excel compatibility

    def _write_search_terms_csv(
        self, writer: Any, search_terms: list[SearchTerm]
    ) -> None:
        """Write search terms data to CSV."""
        # Header
        writer.writerow(
            [
                "Search Term",
                "Campaign",
                "Ad Group",
                "Impressions",
                "Clicks",
                "CTR %",
                "Cost",
                "CPC",
                "Conversions",
                "Conv. Rate %",
                "CPA",
                "Conv. Value",
                "ROAS",
                "Local Intent",
                "Recommendation",
            ]
        )

        # Data rows
        for st in search_terms:
            writer.writerow(
                [
                    st.search_term,
                    st.campaign_name,
                    st.ad_group_name,
                    st.metrics.impressions,
                    st.metrics.clicks,
                    f"{st.metrics.ctr:.2f}",
                    f"${st.metrics.cost:.2f}",
                    f"${st.metrics.cpc:.2f}",
                    f"{st.metrics.conversions:.2f}",
                    f"{st.metrics.conversion_rate:.2f}",
                    f"${st.metrics.cpa:.2f}" if st.metrics.conversions > 0 else "N/A",
                    f"${st.metrics.conversion_value:.2f}",
                    f"{st.metrics.roas:.2f}" if st.metrics.cost > 0 else "N/A",
                    "Yes" if st.is_local_intent else "No",
                    st.recommendation or "",
                ]
            )

    def _export_xlsx(self, data: SearchTermAnalysisResult, **kwargs) -> bytes:
        """Export to Excel format with multiple sheets."""
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Summary sheet
            summary_data = {
                "Metric": [
                    "Analysis Date",
                    "Date Range",
                    "Total Search Terms",
                    "Total Impressions",
                    "Total Clicks",
                    "Total Cost",
                    "Total Conversions",
                    "Overall CTR %",
                    "Overall CPC",
                    "Overall CPA",
                    "Add Candidates",
                    "Negative Candidates",
                    "Review Needed",
                    "Local Intent Terms",
                    "Near Me Terms",
                    "Potential Savings",
                    "Potential Revenue",
                ],
                "Value": [
                    data.created_at.strftime("%Y-%m-%d %H:%M"),
                    f"{data.start_date.date()} to {data.end_date.date()}",
                    data.total_search_terms,
                    data.total_impressions,
                    data.total_clicks,
                    f"${data.total_cost:,.2f}",
                    f"{data.total_conversions:,.2f}",
                    f"{data.overall_ctr:.2f}%",
                    f"${data.overall_cpc:.2f}",
                    f"${data.overall_cpa:.2f}",
                    len(data.add_candidates),
                    len(data.negative_candidates),
                    len(data.review_needed),
                    data.local_intent_terms,
                    data.near_me_terms,
                    f"${data.potential_savings:,.2f}",
                    f"${data.potential_revenue:,.2f}",
                ],
            }

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Add Candidates sheet
            if data.add_candidates:
                add_df = self._search_terms_to_dataframe(data.add_candidates)
                add_df.to_excel(writer, sheet_name="Add Candidates", index=False)

            # Negative Candidates sheet
            if data.negative_candidates:
                neg_df = self._search_terms_to_dataframe(data.negative_candidates)
                neg_df.to_excel(writer, sheet_name="Negative Candidates", index=False)

            # Review Needed sheet (optional)
            if data.review_needed and kwargs.get("include_review", False):
                review_df = self._search_terms_to_dataframe(data.review_needed)
                review_df.to_excel(writer, sheet_name="Review Needed", index=False)

            # Recommendations sheet
            if data.recommendations:
                rec_df = pd.DataFrame(
                    [
                        {
                            "Priority": r.priority,
                            "Type": r.type,
                            "Title": r.title,
                            "Description": r.description,
                        }
                        for r in data.recommendations
                    ]
                )
                rec_df.to_excel(writer, sheet_name="Recommendations", index=False)

            # Format the Excel file
            self._format_excel(writer)

        output.seek(0)
        return output.read()

    def _search_terms_to_dataframe(
        self, search_terms: list[SearchTerm]
    ) -> pd.DataFrame:
        """Convert search terms to pandas DataFrame."""
        data = []
        for st in search_terms:
            data.append(
                {
                    "Search Term": st.search_term,
                    "Campaign": st.campaign_name,
                    "Ad Group": st.ad_group_name,
                    "Impressions": st.metrics.impressions,
                    "Clicks": st.metrics.clicks,
                    "CTR %": round(st.metrics.ctr, 2),
                    "Cost": round(st.metrics.cost, 2),
                    "CPC": round(st.metrics.cpc, 2),
                    "Conversions": round(st.metrics.conversions, 2),
                    "Conv. Rate %": round(st.metrics.conversion_rate, 2),
                    "CPA": round(st.metrics.cpa, 2)
                    if st.metrics.conversions > 0
                    else None,
                    "Conv. Value": round(st.metrics.conversion_value, 2),
                    "ROAS": round(st.metrics.roas, 2) if st.metrics.cost > 0 else None,
                    "Local Intent": "Yes" if st.is_local_intent else "No",
                    "Near Me": "Yes" if st.contains_near_me else "No",
                    "Classification": st.classification if st.classification else "",
                    "Reason": st.classification_reason or "",
                    "Recommendation": st.recommendation or "",
                }
            )

        return pd.DataFrame(data)

    def _format_excel(self, writer: pd.ExcelWriter) -> None:
        """Apply formatting to Excel sheets."""
        # For openpyxl, formatting is done differently
        # We'll skip advanced formatting for now to keep it simple

    def _export_json(self, data: SearchTermAnalysisResult, **kwargs) -> bytes:
        """Export to JSON format."""
        # Convert to dictionary with proper serialization
        export_data = {
            "summary": data.to_summary_dict(),
            "add_candidates": [
                self._search_term_to_dict(st)
                for st in data.add_candidates[: kwargs.get("limit", 100)]
            ],
            "negative_candidates": [
                self._search_term_to_dict(st)
                for st in data.negative_candidates[: kwargs.get("limit", 100)]
            ],
            "recommendations": [
                {
                    "type": r.type,
                    "priority": r.priority,
                    "title": r.title,
                    "description": r.description,
                }
                for r in data.recommendations
            ],
        }

        if kwargs.get("include_review", False):
            export_data["review_needed"] = [
                self._search_term_to_dict(st)
                for st in data.review_needed[: kwargs.get("limit", 50)]
            ]

        # Pretty print JSON
        json_str = json.dumps(export_data, indent=2, default=str)
        return json_str.encode("utf-8")

    def _search_term_to_dict(self, search_term: SearchTerm) -> dict[str, Any]:
        """Convert SearchTerm to dictionary for JSON export."""
        return {
            "search_term": search_term.search_term,
            "campaign": search_term.campaign_name,
            "ad_group": search_term.ad_group_name,
            "metrics": {
                "impressions": search_term.metrics.impressions,
                "clicks": search_term.metrics.clicks,
                "cost": round(search_term.metrics.cost, 2),
                "conversions": round(search_term.metrics.conversions, 2),
                "conversion_value": round(search_term.metrics.conversion_value, 2),
                "ctr": round(search_term.metrics.ctr, 2),
                "cpc": round(search_term.metrics.cpc, 2),
                "cpa": round(search_term.metrics.cpa, 2)
                if search_term.metrics.conversions > 0
                else None,
                "roas": round(search_term.metrics.roas, 2)
                if search_term.metrics.cost > 0
                else None,
            },
            "local_intent": search_term.is_local_intent,
            "contains_near_me": search_term.contains_near_me,
            "classification": search_term.classification
            if search_term.classification
            else None,
            "recommendation": search_term.recommendation,
        }
