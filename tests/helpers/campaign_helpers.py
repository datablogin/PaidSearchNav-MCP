"""Test helper functions for creating Campaign instances."""

from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)


def create_test_campaign(**overrides) -> Campaign:
    """
    Create a test Campaign instance with sensible defaults.

    This helper function reduces code duplication in tests and ensures
    all required fields are provided with appropriate default values.

    Args:
        **overrides: Keyword arguments to override default values

    Returns:
        Campaign instance with the specified values

    Example:
        >>> campaign = create_test_campaign(
        ...     name="My Test Campaign",
        ...     budget_amount=500.0,
        ...     type=CampaignType.PERFORMANCE_MAX
        ... )
    """
    defaults = {
        "campaign_id": "123456789",
        "customer_id": "987654321",
        "name": "Test Campaign",
        "status": CampaignStatus.ENABLED,
        "type": CampaignType.SEARCH,
        "budget_amount": 100.0,
        "budget_currency": "USD",
        "bidding_strategy": BiddingStrategy.TARGET_CPA,
        # Optional fields with sensible defaults
        "impressions": 0,
        "clicks": 0,
        "cost": 0.0,
        "conversions": 0.0,
        "conversion_value": 0.0,
    }

    # Merge defaults with overrides
    campaign_data = {**defaults, **overrides}

    return Campaign(**campaign_data)


def create_test_campaigns_batch(count: int, **common_overrides) -> list[Campaign]:
    """
    Create multiple test Campaign instances with incremental IDs.

    Args:
        count: Number of campaigns to create
        **common_overrides: Common overrides for all campaigns

    Returns:
        List of Campaign instances

    Example:
        >>> campaigns = create_test_campaigns_batch(
        ...     3,
        ...     budget_currency="EUR",
        ...     status=CampaignStatus.PAUSED
        ... )
    """
    campaigns = []
    for i in range(count):
        campaign_overrides = {
            "campaign_id": f"{123456789 + i}",
            "name": f"Test Campaign {i + 1}",
            **common_overrides,
        }
        campaigns.append(create_test_campaign(**campaign_overrides))

    return campaigns
