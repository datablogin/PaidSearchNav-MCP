"""Google Ads platform integration."""

from .auth import OAuth2TokenManager, SecretManagerTokenStorage, TokenData, TokenStorage
from .client import GoogleAdsAPIClient
from .models import GoogleAdsConfig
from .models_extended import (
    AdSchedulePerformance,
    AuctionInsights,
    DevicePerformance,
    DeviceType,
    StorePerformance,
)

__all__ = [
    "OAuth2TokenManager",
    "TokenData",
    "TokenStorage",
    "SecretManagerTokenStorage",
    "GoogleAdsAPIClient",
    "GoogleAdsConfig",
    "DevicePerformance",
    "DeviceType",
    "AdSchedulePerformance",
    "StorePerformance",
    "AuctionInsights",
]
