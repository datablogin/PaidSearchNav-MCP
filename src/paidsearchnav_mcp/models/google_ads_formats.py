"""Google Ads import format specifications."""

from enum import Enum
from typing import Optional


class GoogleAdsFieldLimits:
    """Field length limits for Google Ads imports."""

    CUSTOMER_ID_MAX = 10
    CAMPAIGN_NAME_MAX = 255
    AD_GROUP_NAME_MAX = 255
    KEYWORD_MAX = 80  # Keyword text max length
    URL_MAX = 2048
    DESCRIPTION_MAX = 90
    HEADLINE_MAX = 30


class GoogleAdsMatchType(str, Enum):
    """Valid match types for Google Ads."""

    EXACT = "Exact"
    PHRASE = "Phrase"
    BROAD = "Broad"


class GoogleAdsStatus(str, Enum):
    """Valid statuses for Google Ads entities."""

    ENABLED = "Enabled"
    PAUSED = "Paused"
    REMOVED = "Removed"


class GoogleAdsBidStrategy(str, Enum):
    """Valid bid strategies for Google Ads."""

    MANUAL_CPC = "Manual CPC"
    ENHANCED_CPC = "Enhanced CPC"
    TARGET_CPA = "Target CPA"
    TARGET_ROAS = "Target ROAS"
    MAXIMIZE_CLICKS = "Maximize clicks"
    MAXIMIZE_CONVERSIONS = "Maximize conversions"
    MAXIMIZE_CONVERSION_VALUE = "Maximize conversion value"
    TARGET_IMPRESSION_SHARE = "Target impression share"


class GoogleAdsDevice(str, Enum):
    """Valid device types for bid adjustments."""

    MOBILE = "Mobile"
    DESKTOP = "Desktop"
    TABLET = "Tablet"
    ALL = "All"


class GoogleAdsCSVFormat:
    """CSV format specifications for Google Ads imports."""

    # Column headers for different file types
    KEYWORD_CHANGES_HEADERS = [
        "Customer ID",
        "Campaign",
        "Ad Group",
        "Keyword",
        "Match Type",
        "Status",
        "Max CPC",
        "Final URL",
    ]

    NEGATIVE_KEYWORDS_HEADERS = [
        "Customer ID",
        "Campaign",
        "Ad Group",
        "Keyword",
        "Match Type",
    ]

    BID_ADJUSTMENTS_HEADERS = [
        "Customer ID",
        "Campaign",
        "Location",
        "Device",
        "Bid Adjustment",
    ]

    CAMPAIGN_CHANGES_HEADERS = [
        "Customer ID",
        "Campaign",
        "Status",
        "Budget",
        "Bid Strategy",
        "Target CPA",
        "Target ROAS",
    ]

    # Special values
    CAMPAIGN_LEVEL_NEGATIVE = "[Campaign]"
    AD_GROUP_LEVEL_NEGATIVE = "[Ad group]"

    @staticmethod
    def format_currency(value: Optional[float]) -> str:
        """Format currency values for Google Ads import."""
        if value is None:
            return ""
        return f"{value:.2f}"

    @staticmethod
    def format_percentage(value: float, include_sign: bool = True) -> str:
        """Format percentage values for bid adjustments."""
        if value == 0:
            return "0%"
        if include_sign and value > 0:
            return f"+{value:.0f}%"
        return f"{value:.0f}%"

    @staticmethod
    def validate_customer_id(customer_id: str) -> bool:
        """Validate Google Ads customer ID format."""
        # Customer ID should be 10 digits, no hyphens
        if not customer_id:
            return False
        # Remove hyphens if present
        clean_id = customer_id.replace("-", "")
        return len(clean_id) == 10 and clean_id.isdigit()

    @staticmethod
    def clean_customer_id(customer_id: str) -> str:
        """Clean customer ID by removing hyphens."""
        return customer_id.replace("-", "")


class GoogleAdsValidation:
    """Validation rules for Google Ads data."""

    # Characters that need special handling
    SPECIAL_CHARS_TO_ESCAPE = ['"', ",", "\n", "\r"]

    # Invalid characters in keywords
    INVALID_KEYWORD_CHARS = [
        "!",
        "@",
        "%",
        "^",
        "*",
        "(",
        ")",
        "=",
        "{",
        "}",
        "[",
        "]",
        "~",
        "`",
    ]

    @staticmethod
    def escape_csv_value(value: str) -> str:
        """Escape special characters for CSV format."""
        if any(char in value for char in GoogleAdsValidation.SPECIAL_CHARS_TO_ESCAPE):
            # Escape quotes by doubling them
            value = value.replace('"', '""')
            # Wrap in quotes
            return f'"{value}"'
        return value

    @staticmethod
    def validate_keyword(keyword: str) -> tuple[bool, Optional[str]]:
        """
        Validate a keyword for Google Ads.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not keyword:
            return False, "Keyword cannot be empty"

        if len(keyword) > GoogleAdsFieldLimits.KEYWORD_MAX:
            return (
                False,
                f"Keyword exceeds {GoogleAdsFieldLimits.KEYWORD_MAX} characters",
            )

        # Check for invalid characters
        for char in GoogleAdsValidation.INVALID_KEYWORD_CHARS:
            if char in keyword:
                return False, f"Keyword contains invalid character: {char}"

        # Check for excessive spaces
        if "  " in keyword:
            return False, "Keyword contains multiple consecutive spaces"

        return True, None

    @staticmethod
    def validate_campaign_name(name: str) -> tuple[bool, Optional[str]]:
        """Validate campaign name."""
        if not name:
            return False, "Campaign name cannot be empty"

        if len(name) > GoogleAdsFieldLimits.CAMPAIGN_NAME_MAX:
            return (
                False,
                f"Campaign name exceeds {GoogleAdsFieldLimits.CAMPAIGN_NAME_MAX} characters",
            )

        return True, None

    @staticmethod
    def validate_ad_group_name(name: str) -> tuple[bool, Optional[str]]:
        """Validate ad group name."""
        if not name:
            return False, "Ad group name cannot be empty"

        if len(name) > GoogleAdsFieldLimits.AD_GROUP_NAME_MAX:
            return (
                False,
                f"Ad group name exceeds {GoogleAdsFieldLimits.AD_GROUP_NAME_MAX} characters",
            )

        return True, None

    @staticmethod
    def validate_url(url: Optional[str]) -> tuple[bool, Optional[str]]:
        """Validate URL for Google Ads."""
        if not url:
            return True, None  # URL is optional

        if len(url) > GoogleAdsFieldLimits.URL_MAX:
            return False, f"URL exceeds {GoogleAdsFieldLimits.URL_MAX} characters"

        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"

        return True, None

    @staticmethod
    def validate_bid(bid: Optional[float]) -> tuple[bool, Optional[str]]:
        """Validate bid amount."""
        if bid is None:
            return True, None  # Bid is optional

        if bid < 0:
            return False, "Bid cannot be negative"

        if bid > 10000:  # Reasonable upper limit
            return False, "Bid exceeds maximum allowed value"

        return True, None


class GoogleAdsErrorCodes:
    """Common error codes and messages from Google Ads."""

    DUPLICATE_KEYWORD = "DUPLICATE_KEYWORD"
    INVALID_MATCH_TYPE = "INVALID_MATCH_TYPE"
    INVALID_STATUS = "INVALID_STATUS"
    BUDGET_TOO_LOW = "BUDGET_TOO_LOW"
    INVALID_BID_STRATEGY = "INVALID_BID_STRATEGY"
    KEYWORD_CONFLICT = "KEYWORD_CONFLICT"
    NEGATIVE_CONFLICT = "NEGATIVE_CONFLICT"

    ERROR_MESSAGES = {
        DUPLICATE_KEYWORD: "This keyword already exists in the ad group",
        INVALID_MATCH_TYPE: "Invalid match type specified",
        INVALID_STATUS: "Invalid status value",
        BUDGET_TOO_LOW: "Budget is below minimum threshold",
        INVALID_BID_STRATEGY: "Invalid or unsupported bid strategy",
        KEYWORD_CONFLICT: "Keyword conflicts with existing negative keyword",
        NEGATIVE_CONFLICT: "Negative keyword blocks existing positive keyword",
    }


class GoogleAdsFileRequirements:
    """File requirements for Google Ads imports."""

    MAX_FILE_SIZE_MB = 100
    MAX_ROWS_PER_FILE = 100000
    ENCODING = "UTF-8"
    DELIMITER = ","
    QUOTE_CHAR = '"'
    LINE_TERMINATOR = "\r\n"  # Windows-style for Google Ads compatibility
    INCLUDE_BOM = True  # UTF-8 BOM for Excel compatibility

    @staticmethod
    def validate_file_size(size_bytes: int) -> bool:
        """Check if file size is within limits."""
        max_bytes = GoogleAdsFileRequirements.MAX_FILE_SIZE_MB * 1024 * 1024
        return size_bytes <= max_bytes
