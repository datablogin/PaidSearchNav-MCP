"""CSV formatting utilities for Performance Max Google Ads Scripts data extraction.

This module ensures that Performance Max data extracted by Google Ads Scripts
is formatted to be compatible with existing PaidSearchNav CSV parsers and S3 storage.
"""

import csv
import json
import logging
from datetime import datetime
from io import StringIO
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class PerformanceMaxCSVFormatter:
    """Formats Performance Max Google Ads Scripts output to match expected CSV formats."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def format_performance_max_monitoring_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format Performance Max monitoring data to CSV format.

        Args:
            data: List of Performance Max campaign performance data

        Returns:
            CSV formatted string
        """
        headers = [
            "Campaign ID",
            "Campaign Name",
            "Campaign Type",
            "Status",
            "Bidding Strategy",
            "Target ROAS",
            "Target CPA",
            "Daily Budget",
            "Cost",
            "Impressions",
            "Clicks",
            "Conversions",
            "Conversion Value",
            "All Conversions",
            "View-through Conversions",
            "CTR (%)",
            "CPC",
            "CPA",
            "ROAS",
            "Conversion Rate (%)",
            "Performance Flags",
            "Date",
        ]

        return self._format_to_csv(headers, data, self._map_pmax_monitoring_row)

    def format_asset_optimization_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format Performance Max asset optimization data to CSV format.

        Args:
            data: List of asset optimization analysis data

        Returns:
            CSV formatted string
        """
        headers = [
            "Asset ID",
            "Asset Name",
            "Asset Type",
            "Field Type",
            "Asset Group ID",
            "Asset Group Name",
            "Campaign ID",
            "Campaign Name",
            "Impressions",
            "Clicks",
            "Conversions",
            "CTR (%)",
            "Conversion Rate (%)",
            "Performance Category",
            "Ad Strength",
            "Needs Improvement",
            "Improvement Reason",
            "Date",
        ]

        return self._format_to_csv(headers, data, self._map_asset_optimization_row)

    def format_geographic_performance_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format Performance Max geographic performance data to CSV format.

        Args:
            data: List of geographic performance analysis data

        Returns:
            CSV formatted string
        """
        headers = [
            "Location ID",
            "Location Type",
            "Location Name",
            "State",
            "Is Priority Location",
            "Campaign Count",
            "Total Impressions",
            "Total Clicks",
            "Total Cost",
            "Total Conversions",
            "Total Conversion Value",
            "All Conversions",
            "View-through Conversions",
            "CTR (%)",
            "CPC",
            "CPA",
            "ROAS",
            "Conversion Rate (%)",
            "Performance Category",
            "Date Range",
        ]

        return self._format_to_csv(headers, data, self._map_geographic_performance_row)

    def format_bidding_optimization_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format Performance Max bidding optimization data to CSV format.

        Args:
            data: List of bidding strategy analysis data

        Returns:
            CSV formatted string
        """
        headers = [
            "Strategy ID",
            "Strategy Name",
            "Strategy Type",
            "Campaign ID",
            "Campaign Name",
            "Target ROAS",
            "Actual ROAS",
            "Target CPA",
            "Actual CPA",
            "Total Cost",
            "Total Conversions",
            "Total Conversion Value",
            "CTR (%)",
            "Conversion Rate (%)",
            "ROAS Performance Ratio",
            "CPA Performance Ratio",
            "ROAS Target Met",
            "CPA Target Met",
            "Effectiveness Rating",
            "Impression Share (%)",
            "Budget Lost IS (%)",
            "Rank Lost IS (%)",
            "Date Range",
        ]

        return self._format_to_csv(headers, data, self._map_bidding_optimization_row)

    def format_cross_campaign_analysis_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format cross-campaign analysis data to CSV format.

        Args:
            data: List of cross-campaign analysis data

        Returns:
            CSV formatted string
        """
        headers = [
            "Search Term",
            "Performance Max Campaign ID",
            "Performance Max Campaign Name",
            "Search Campaign ID",
            "Search Campaign Name",
            "Performance Max Cost",
            "Search Cost",
            "Total Cost",
            "Performance Max Conversions",
            "Search Conversions",
            "Performance Max CPA",
            "Search CPA",
            "Performance Max ROAS",
            "Search ROAS",
            "Better Performer",
            "Overlap Severity",
            "Recommendation",
            "Date Range",
        ]

        return self._format_to_csv(headers, data, self._map_cross_campaign_row)

    def format_search_term_insights_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format Performance Max search term insights to CSV format.

        Args:
            data: List of search term insights data

        Returns:
            CSV formatted string
        """
        headers = [
            "Search Term",
            "Campaign ID",
            "Campaign Name",
            "Ad Group ID",
            "Ad Group Name",
            "Status",
            "Impressions",
            "Clicks",
            "Cost",
            "Conversions",
            "Conversion Value",
            "CTR (%)",
            "CPC",
            "CPA",
            "ROAS",
            "Local Intent",
            "Brand Intent",
            "Commercial Intent",
            "Specific Location",
            "Local Intent Type",
            "Negative Candidate",
            "Negative Reason",
            "Search Port Candidate",
            "Port Reason",
            "Date",
        ]

        return self._format_to_csv(headers, data, self._map_search_term_insights_row)

    def _format_to_csv(
        self, headers: List[str], data: List[Dict[str, Any]], row_mapper: Callable
    ) -> str:
        """Generic CSV formatting method.

        Args:
            headers: CSV column headers
            data: Data to format
            row_mapper: Function to map data row to CSV row

        Returns:
            CSV formatted string
        """
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Write headers
        writer.writerow(headers)

        # Write data rows
        for item in data:
            try:
                row = row_mapper(item)
                writer.writerow(row)
            except Exception as e:
                self.logger.warning(f"Error formatting row: {e}, skipping row")
                continue

        return output.getvalue()

    def _map_pmax_monitoring_row(self, item: Dict[str, Any]) -> List[str]:
        """Map Performance Max monitoring data to CSV row."""
        return [
            str(item.get("campaignId", "")),
            str(item.get("campaignName", "")),
            str(item.get("campaignType", "PERFORMANCE_MAX")),
            str(item.get("status", "")),
            str(item.get("biddingStrategy", "")),
            f"{item.get('targetRoas', 0):.2f}",
            f"{item.get('targetCpa', 0):.2f}",
            f"{item.get('dailyBudget', 0):.2f}",
            f"{item.get('cost', 0):.2f}",
            str(item.get("impressions", 0)),
            str(item.get("clicks", 0)),
            f"{item.get('conversions', 0):.2f}",
            f"{item.get('conversionValue', 0):.2f}",
            f"{item.get('allConversions', 0):.2f}",
            f"{item.get('viewThroughConversions', 0):.2f}",
            f"{item.get('ctr', 0):.2f}",
            f"{item.get('cpc', 0):.2f}",
            f"{item.get('cpa', 0):.2f}",
            f"{item.get('roas', 0):.2f}",
            f"{item.get('conversionRate', 0):.2f}",
            ";".join(item.get("performanceFlags", [])),
            str(item.get("date", "")),
        ]

    def _map_asset_optimization_row(self, item: Dict[str, Any]) -> List[str]:
        """Map asset optimization data to CSV row."""
        return [
            str(item.get("assetId", "")),
            str(item.get("assetName", "")),
            str(item.get("assetType", "")),
            str(item.get("fieldType", "")),
            str(item.get("assetGroupId", "")),
            str(item.get("assetGroupName", "")),
            str(item.get("campaignId", "")),
            str(item.get("campaignName", "")),
            str(item.get("impressions", 0)),
            str(item.get("clicks", 0)),
            f"{item.get('conversions', 0):.2f}",
            f"{item.get('ctr', 0):.2f}",
            f"{item.get('conversionRate', 0):.2f}",
            str(item.get("performanceCategory", "")),
            str(item.get("adStrength", "")),
            str(item.get("needsImprovement", False)),
            str(item.get("improvementReason", "")),
            str(item.get("date", "")),
        ]

    def _map_geographic_performance_row(self, item: Dict[str, Any]) -> List[str]:
        """Map geographic performance data to CSV row."""
        target_match = item.get("targetLocationMatch", {})
        return [
            str(item.get("locationId", "")),
            str(item.get("locationType", "")),
            str(target_match.get("name", "")),
            str(target_match.get("state", "")),
            str(target_match.get("isPriority", False)),
            str(len(item.get("campaignIds", []))),
            str(item.get("totalImpressions", 0)),
            str(item.get("totalClicks", 0)),
            f"{item.get('totalCost', 0):.2f}",
            f"{item.get('totalConversions', 0):.2f}",
            f"{item.get('totalConversionValue', 0):.2f}",
            f"{item.get('allConversions', 0):.2f}",
            f"{item.get('viewThroughConversions', 0):.2f}",
            f"{item.get('ctr', 0):.2f}",
            f"{item.get('cpc', 0):.2f}",
            f"{item.get('cpa', 0):.2f}",
            f"{item.get('roas', 0):.2f}",
            f"{item.get('conversionRate', 0):.2f}",
            str(item.get("performanceCategory", "")),
            str(item.get("dateRange", "")),
        ]

    def _map_bidding_optimization_row(self, item: Dict[str, Any]) -> List[str]:
        """Map bidding optimization data to CSV row."""
        return [
            str(item.get("strategyId", "")),
            str(item.get("strategyName", "")),
            str(item.get("strategyType", "")),
            str(item.get("campaignId", "")),
            str(item.get("campaignName", "")),
            f"{item.get('targetRoas', 0):.2f}",
            f"{item.get('actualRoas', 0):.2f}",
            f"{item.get('targetCpa', 0):.2f}",
            f"{item.get('actualCpa', 0):.2f}",
            f"{item.get('totalCost', 0):.2f}",
            f"{item.get('totalConversions', 0):.2f}",
            f"{item.get('totalConversionValue', 0):.2f}",
            f"{item.get('ctr', 0):.2f}",
            f"{item.get('conversionRate', 0):.2f}",
            f"{item.get('roasPerformanceRatio', 0):.2f}",
            f"{item.get('cpaPerformanceRatio', 0):.2f}",
            str(item.get("roasTargetMet", False)),
            str(item.get("cpaTargetMet", False)),
            str(item.get("effectiveness", "")),
            f"{item.get('impressionShare', 0):.2f}",
            f"{item.get('budgetLostIS', 0):.2f}",
            f"{item.get('rankLostIS', 0):.2f}",
            str(item.get("dateRange", "")),
        ]

    def _map_cross_campaign_row(self, item: Dict[str, Any]) -> List[str]:
        """Map cross-campaign analysis data to CSV row."""
        return [
            str(item.get("searchTerm", "")),
            str(item.get("pmaxCampaignId", "")),
            str(item.get("pmaxCampaignName", "")),
            str(item.get("searchCampaignId", "")),
            str(item.get("searchCampaignName", "")),
            f"{item.get('pmaxCost', 0):.2f}",
            f"{item.get('searchCost', 0):.2f}",
            f"{item.get('totalCost', 0):.2f}",
            f"{item.get('pmaxConversions', 0):.2f}",
            f"{item.get('searchConversions', 0):.2f}",
            f"{item.get('pmaxCpa', 0):.2f}",
            f"{item.get('searchCpa', 0):.2f}",
            f"{item.get('pmaxRoas', 0):.2f}",
            f"{item.get('searchRoas', 0):.2f}",
            str(item.get("betterPerformer", "")),
            str(item.get("overlapSeverity", "")),
            str(item.get("recommendation", "")),
            str(item.get("dateRange", "")),
        ]

    def _map_search_term_insights_row(self, item: Dict[str, Any]) -> List[str]:
        """Map search term insights data to CSV row."""
        return [
            str(item.get("searchTerm", "")),
            str(item.get("campaignId", "")),
            str(item.get("campaignName", "")),
            str(item.get("adGroupId", "")),
            str(item.get("adGroupName", "")),
            str(item.get("status", "")),
            str(item.get("impressions", 0)),
            str(item.get("clicks", 0)),
            f"{item.get('cost', 0):.2f}",
            f"{item.get('conversions', 0):.2f}",
            f"{item.get('conversionValue', 0):.2f}",
            f"{item.get('ctr', 0):.2f}",
            f"{item.get('cpc', 0):.2f}",
            f"{item.get('cpa', 0):.2f}",
            f"{item.get('roas', 0):.2f}",
            str(item.get("localIntent", False)),
            str(item.get("brandIntent", False)),
            str(item.get("commercialIntent", False)),
            str(item.get("specificLocation", "")),
            str(item.get("intentType", "")),
            str(item.get("negativeCandidate", False)),
            str(item.get("negativeReason", "")),
            str(item.get("searchPortCandidate", False)),
            str(item.get("portReason", "")),
            str(item.get("date", "")),
        ]

    def create_summary_report(self, results: Dict[str, Any]) -> str:
        """Create a summary report of Performance Max analysis results.

        Args:
            results: Dictionary containing all analysis results

        Returns:
            JSON formatted summary report
        """
        summary = {
            "execution_date": datetime.utcnow().isoformat(),
            "analysis_type": "performance_max_comprehensive",
            "summary": {
                "campaigns_analyzed": results.get("campaigns_analyzed", 0),
                "asset_groups_analyzed": results.get("asset_groups_analyzed", 0),
                "search_terms_analyzed": results.get("search_terms_analyzed", 0),
                "geographic_locations_analyzed": results.get(
                    "geographic_locations_analyzed", 0
                ),
                "overlapping_terms_found": results.get("overlapping_terms_found", 0),
                "recommendations_generated": results.get(
                    "recommendations_generated", 0
                ),
                "conflicts_identified": results.get("conflicts_identified", 0),
            },
            "key_findings": results.get("key_findings", []),
            "top_recommendations": results.get("top_recommendations", []),
            "performance_metrics": {
                "average_pmax_roas": results.get("average_pmax_roas", 0.0),
                "average_search_roas": results.get("average_search_roas", 0.0),
                "total_spend": results.get("total_spend", 0.0),
                "total_conversions": results.get("total_conversions", 0.0),
                "potential_savings": results.get("potential_savings", 0.0),
            },
            "data_quality": {
                "data_completeness": results.get("data_completeness", 0.0),
                "processing_errors": results.get("processing_errors", []),
                "warnings": results.get("warnings", []),
            },
        }

        return json.dumps(summary, indent=2)

    def format_for_s3_storage(
        self,
        data_type: str,
        data: List[Dict[str, Any]],
        customer_id: str,
        date_range: str,
    ) -> Dict[str, str]:
        """Format data for S3 storage with appropriate file naming.

        Args:
            data_type: Type of data (monitoring, assets, geographic, etc.)
            data: Data to format
            customer_id: Google Ads customer ID
            date_range: Date range for the analysis

        Returns:
            Dictionary with filename and CSV content
        """
        formatters = {
            "monitoring": self.format_performance_max_monitoring_csv,
            "assets": self.format_asset_optimization_csv,
            "geographic": self.format_geographic_performance_csv,
            "bidding": self.format_bidding_optimization_csv,
            "cross_campaign": self.format_cross_campaign_analysis_csv,
            "search_terms": self.format_search_term_insights_csv,
        }

        if data_type not in formatters:
            raise ValueError(f"Unknown data type: {data_type}")

        csv_content = formatters[data_type](data)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"pmax_{data_type}_{customer_id}_{date_range}_{timestamp}.csv"

        return {
            "filename": filename,
            "content": csv_content,
            "content_type": "text/csv",
        }
