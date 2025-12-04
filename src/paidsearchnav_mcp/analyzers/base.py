"""Base analyzer class for PaidSearchNav MCP server."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AnalysisSummary(BaseModel):
    """Standard format for analysis summaries.

    This model ensures all analyzers return consistent, compact summaries
    that fit within Claude Desktop's context window.
    """

    total_records_analyzed: int = Field(description="Total number of records analyzed")
    estimated_monthly_savings: float = Field(
        description="Estimated monthly savings from implementing recommendations"
    )
    primary_issue: str = Field(description="Primary issue identified in the analysis")
    top_recommendations: list[dict[str, Any]] = Field(
        description="Top 10 recommendations with dollar impact"
    )
    implementation_steps: list[str] = Field(
        description="Prioritized implementation steps"
    )
    analysis_period: str = Field(description="Date range of the analysis")
    customer_id: str = Field(description="Google Ads customer ID")


class BaseAnalyzer(ABC):
    """Base class for all analyzers.

    Analyzers perform server-side analysis and return only summaries,
    not raw data. This prevents context window exhaustion in Claude Desktop.
    """

    @abstractmethod
    async def analyze(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        **kwargs: Any,
    ) -> AnalysisSummary:
        """Perform analysis and return summary.

        Returns only:
        - Executive summary (5-10 lines)
        - Top 10 recommendations with dollar impact
        - Implementation steps

        Does NOT return raw data.

        Args:
            customer_id: Google Ads customer ID (10 digits, no dashes)
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)
            **kwargs: Additional analyzer-specific parameters

        Returns:
            AnalysisSummary with top recommendations only
        """
        pass

    def _format_currency(self, amount: float) -> str:
        """Format dollar amounts consistently.

        Args:
            amount: Dollar amount to format

        Returns:
            Formatted currency string (e.g., "$1,234.56")
        """
        return f"${amount:,.2f}"

    def _calculate_savings(self, current_cost: float, optimized_cost: float) -> float:
        """Calculate savings with conservative estimates.

        Args:
            current_cost: Current cost
            optimized_cost: Estimated optimized cost

        Returns:
            Savings amount (always >= 0)
        """
        return max(0, current_cost - optimized_cost)
