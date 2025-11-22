"""Field mappings for different CSV file types from Google Ads."""

from typing import Dict

# Field mappings for different Google Ads CSV exports
FIELD_MAPPINGS = {
    "keywords": {
        # Identifiers
        "Keyword ID": "keyword_id",
        "Campaign ID": "campaign_id",
        "Campaign": "campaign_name",
        "Ad group ID": "ad_group_id",
        "Ad group": "ad_group_name",
        # Keyword details
        "Keyword": "text",
        "Match type": "match_type",
        "Status": "status",
        # Bidding
        "Max. CPC": "cpc_bid",
        "Final URL": "final_url",
        # Quality metrics
        "Quality Score": "quality_score",
        "Landing page experience": "landing_page_experience",
        "Expected CTR": "expected_ctr",
        "Ad relevance": "ad_relevance",
        # Performance metrics
        "Impr.": "impressions",
        "Impressions": "impressions",  # Alternative format
        "Clicks": "clicks",
        "Cost": "cost",
        "Conversions": "conversions",
        "Conversion value": "conversion_value",
        # Position metrics
        "Avg. position": "avg_position",
        "Top Impr. %": "top_impression_percentage",
        "Abs. Top Impr. %": "absolute_top_impression_percentage",
        # Computed metrics (these are typically calculated, not imported)
        "CTR": "ctr",
        "Avg. CPC": "avg_cpc",
        "Conv. rate": "conversion_rate",
        "Cost / conv.": "cpa",
    },
    "search_terms": {
        # Identifiers
        "Campaign ID": "campaign_id",
        "Campaign": "campaign_name",
        "Ad group ID": "ad_group_id",
        "Ad group": "ad_group_name",
        # Search term details
        "Search term": "search_term",
        "Keyword ID": "keyword_id",
        "Keyword": "keyword_text",
        "Match type": "match_type",
        # Performance metrics (nested under metrics object)
        "Impr.": "metrics.impressions",
        "Clicks": "metrics.clicks",
        "Cost": "metrics.cost",
        "Conversions": "metrics.conversions",
        "Conversion value": "metrics.conversion_value",
        # Computed metrics
        "CTR": "metrics.ctr",
        "Avg. CPC": "metrics.cpc",
        "Conv. rate": "metrics.conversion_rate",
        "Cost / conv.": "metrics.cpa",
        "ROAS": "metrics.roas",
    },
    "geo_performance": {
        # Identifiers
        "Customer ID": "customer_id",
        "Campaign ID": "campaign_id",
        "Campaign": "campaign_name",
        # Geographic identifiers
        "Location type": "geographic_level",
        "User location": "geographic_level",  # Alternative name
        "Geographic location": "geographic_level",  # Alternative name
        "Location": "location_name",
        "Location name": "location_name",  # Alternative name
        "Location ID": "location_id",
        "Country": "country_code",
        "Country name": "country_code",  # Alternative name
        "Region": "region_code",
        "Region name": "region_code",  # Alternative name
        "State": "region_code",  # Alternative name
        "City": "city",
        "City name": "city",  # Alternative name
        "Postal code": "zip_code",
        "Zip code": "zip_code",  # Alternative name
        "ZIP code": "zip_code",  # Alternative name
        # Distance data
        "Distance": "distance_miles",
        "Distance (miles)": "distance_miles",  # Alternative name
        "Business location": "business_location",
        # Performance metrics
        "Impr.": "impressions",
        "Impressions": "impressions",  # Alternative name
        "Clicks": "clicks",
        "Conversions": "conversions",
        "Conv.": "conversions",  # Alternative name
        "Cost": "cost",
        "Revenue": "revenue",
        "Conversion value": "conversion_value",  # Standard name
        "Conv. value": "conversion_value",  # Alternative name
        # Computed metrics
        "CTR": "ctr",
        "Click-through rate": "ctr",  # Alternative name
        "Conv. rate": "conversion_rate",
        "Conversion rate": "conversion_rate",  # Alternative name
        "Cost / conv.": "cpa",
        "Cost per conversion": "cpa",  # Alternative name
        "CPA": "cpa",  # Alternative name
        "ROAS": "roas",
        "Return on ad spend": "roas",  # Alternative name
        # Additional metrics that might appear
        "Avg. CPC": "avg_cpc",
        "Average CPC": "avg_cpc",  # Alternative name
        "Total conv. value": "conversion_value",  # Alternative name
    },
    "campaigns": {
        # Identifiers and basic info
        "Campaign": "name",
        "Campaign status": "status",
        "Campaign state": "status",  # Alternative field name
        "Campaign type": "type",
        # Budget information
        "Budget": "budget_amount",
        "Currency code": "budget_currency",
        "Bid strategy type": "bidding_strategy",
        # Performance metrics
        "Impr.": "impressions",
        "Impressions": "impressions",  # Alternative format
        "Clicks": "clicks",
        "Cost": "cost",
        "Conversions": "conversions",
        "Conv. rate": "conversion_rate",
        "Conv. value": "conversion_value",
        "Avg. CPC": "avg_cpc",
        # Additional fields that might be present
        "Search Impr. share": "search_impression_share",
    },
    "ad_groups": {
        "Campaign": "campaign_name",
        "Ad group": "ad_group_name",
        "Ad group state": "ad_group_status",
        "Ad group status": "ad_group_status",
        "Default max. CPC": "default_max_cpc",
        "Max. CPM": "max_cpm",
        "Target CPA": "target_cpa",
        "Target ROAS": "target_roas",
        "Target CPM": "target_cpm",
        "Status": "status",
        "Status reasons": "status_reasons",
        "Ad group type": "ad_group_type",
        "Currency code": "currency_code",
        "Avg. CPM": "avg_cpm",
        "Impr.": "impressions",
        "Interactions": "interactions",
        "Interaction rate": "interaction_rate",
        "Avg. cost": "avg_cost",
        "Cost": "cost",
        "Clicks": "clicks",
        "Conv. rate": "conversion_rate",
        "Conv. value": "conversion_value",
        "Conv. value / cost": "conversion_value_per_cost",
        "Conversions": "conversions",
        "Avg. CPC": "avg_cpc",
        "Cost / conv.": "cost_per_conversion",
    },
    "negative_keywords": {
        # Identifiers
        "Campaign ID": "campaign_id",
        "Campaign": "campaign_name",
        "Ad group ID": "ad_group_id",
        "Ad group": "ad_group_name",
        # Negative keyword details
        "Negative keyword": "text",
        "Keyword or list": "keyword_or_list",  # Additional field from fitness connection export
        "Match type": "match_type",
        "Level": "level",  # Campaign or Ad group
        # For shared negative lists
        "Negative keyword list": "shared_set_name",
        "Shared library": "shared_set_name",  # Alternative name
        # Status
        "Status": "status",
    },
    "device": {
        # Device information
        "Device": "device",
        "Level": "level",
        "Campaign": "campaign_name",
        "Ad group": "ad_group_name",
        "Bid adj.": "bid_adjustment",
        "Ad group bid adj.": "ad_group_bid_adjustment",
        # Performance metrics
        "Clicks": "clicks",
        "Impr.": "impressions",
        "CTR": "ctr",
        "Currency code": "currency_code",
        "Avg. CPC": "avg_cpc",
        "Cost": "cost",
        "Conv. rate": "conversion_rate",
        "Conversions": "conversions",
        "Cost / conv.": "cpa",
    },
    "ad_schedule": {
        # Schedule information
        "Day & time": "day_time",
        "Bid adj.": "bid_adjustment",
        # Performance metrics
        "Clicks": "clicks",
        "Impr.": "impressions",
        "CTR": "ctr",
        "Currency code": "currency_code",
        "Avg. CPC": "avg_cpc",
        "Cost": "cost",
        "Conv. rate": "conversion_rate",
        "Conversions": "conversions",
        "Cost / conv.": "cpa",
    },
    "per_store": {
        # Store information
        "Store locations": "store_name",
        "address_line_1": "address_line_1",
        "address_line_2": "address_line_2",
        "city": "city",
        "country_code": "country_code",
        "phone_number": "phone_number",
        "postal_code": "postal_code",
        "province": "state",
        # Local performance metrics
        "Local reach (impressions)": "local_impressions",
        "Store visits": "store_visits",
        "Call clicks": "call_clicks",
        "Driving directions": "driving_directions",
        "Website visits": "website_visits",
    },
    "auction_insights": {
        # Competitor information
        "Display URL domain": "competitor_domain",
        "Impr. share": "impression_share",
        "Overlap rate": "overlap_rate",
        "Top of page rate": "top_of_page_rate",
        "Abs. Top of page rate": "abs_top_of_page_rate",
        "Outranking share": "outranking_share",
        "Position above rate": "position_above_rate",
    },
    # UI Export formats (Google Ads interface downloads) - These don't include ID fields
    "keywords_ui": {
        # Keyword details (no IDs available)
        "Keyword": "text",
        "Match type": "match_type",
        "Campaign": "campaign_name",
        "Ad group": "ad_group_name",
        "Status": "status",
        "Keyword status": "status",  # Alternative field name in UI exports
        # Bidding
        "Max. CPC": "cpc_bid",
        "Final URL": "final_url",
        "Mobile final URL": "mobile_final_url",
        # Quality metrics
        "Quality Score": "quality_score",
        "Landing page exp.": "landing_page_experience",
        "Expected CTR": "expected_ctr",
        "Ad relevance": "ad_relevance",
        # Performance metrics
        "Impr.": "impressions",
        "Clicks": "clicks",
        "Cost": "cost",
        "Conversions": "conversions",
        "Conv. value": "conversion_value",
        "Conversion value": "conversion_value",  # Alternative name
        # Position metrics
        "Avg. position": "avg_position",
        "Top Impr. %": "top_impression_percentage",
        "Abs. Top Impr. %": "absolute_top_impression_percentage",
        # Computed metrics
        "CTR": "ctr",
        "Avg. CPC": "avg_cpc",
        "Conv. rate": "conversion_rate",
        "Cost / conv.": "cpa",
        "Value / conv.": "value_per_conversion",
        "Conv. value / cost": "conversion_value_per_cost",
        # Additional UI export fields
        "Interactions": "interactions",
        "Interaction rate": "interaction_rate",
        "Avg. cost": "avg_cost",
        "Avg. CPM": "avg_cpm",
        "Status reasons": "status_reasons",
        "Currency code": "currency_code",
    },
    "search_terms_ui": {
        # Search term details (no IDs available)
        "Search term": "search_term",
        "Match type": "match_type",
        "Campaign": "campaign_name",
        "Ad group": "ad_group_name",
        "Keyword": "keyword_text",  # Triggering keyword
        "Added/Excluded": "added_excluded_status",
        "Campaign type": "campaign_type",
        # Performance metrics (flat structure for UI exports)
        "Impr.": "impressions",
        "Clicks": "clicks",
        "Cost": "cost",
        "Conversions": "conversions",
        "Conv. value": "conversion_value",
        "Conversion value": "conversion_value",  # Alternative name
        # Computed metrics
        "CTR": "ctr",
        "Avg. CPC": "avg_cpc",
        "Conv. rate": "conversion_rate",
        "Cost / conv.": "cpa",
        "ROAS": "roas",
        # Additional UI export fields
        "Interactions": "interactions",
        "Interaction rate": "interaction_rate",
        "Avg. cost": "avg_cost",
        "Avg. CPM": "avg_cpm",
        "Currency code": "currency_code",
    },
    "negative_keywords_ui": {
        # Negative keyword details (no IDs available)
        "Negative keyword": "text",
        "Match type": "match_type",
        "Campaign": "campaign_name",
        "Ad group": "ad_group_name",
        "Level": "level",  # Campaign or Ad group level
        "Status": "status",
        # For shared negative lists
        "Negative keyword list": "shared_set_name",
        "Shared library": "shared_set_name",  # Alternative name
        "Keyword or list": "keyword_or_list",
    },
    "default": {},  # No mapping for default, use original field names
}


def detect_export_format(csv_headers: list[str], file_type: str) -> str:
    """Detect whether CSV is from API export or UI export based on headers.

    Args:
        csv_headers: List of headers from the CSV file.
        file_type: Type of CSV file (e.g., 'keywords', 'search_terms').

    Returns:
        File type with format suffix: 'keywords_ui', 'search_terms_ui', or original file_type for API exports.
    """
    # Check for ID fields that indicate API export
    id_indicators = [
        "Keyword ID",
        "Campaign ID",
        "Ad group ID",
        "Customer ID",
        "Location ID",
    ]

    has_id_fields = any(header in csv_headers for header in id_indicators)

    # If we have ID fields, it's likely an API export
    if has_id_fields:
        return file_type

    # Check for UI export indicators
    ui_indicators = {
        "keywords": [
            "Keyword status",
            "Status reasons",
        ],  # UI exports often have "Keyword status" instead of just "Status"
        "search_terms": [
            "Added/Excluded",
            "Campaign type",
        ],  # UI exports have these additional fields
        "negative_keywords": [
            "Level",
            "Keyword or list",
        ],  # UI exports structure negative keywords differently
    }

    if file_type in ui_indicators:
        ui_fields = ui_indicators[file_type]
        has_ui_fields = any(header in csv_headers for header in ui_fields)

        if has_ui_fields:
            return f"{file_type}_ui"

    # Check if we have basic required fields for UI export
    basic_required = {
        "keywords": ["Keyword", "Match type", "Campaign", "Ad group"],
        "search_terms": ["Search term", "Match type", "Campaign", "Ad group"],
        "negative_keywords": ["Negative keyword", "Match type"],
    }

    if file_type in basic_required:
        required_fields = basic_required[file_type]
        has_basic_fields = all(header in csv_headers for header in required_fields)

        # If we have basic fields but no ID fields, assume it's UI export
        if has_basic_fields and not has_id_fields:
            return f"{file_type}_ui"

    # Default to original file type (API export)
    return file_type


def get_field_mapping(
    file_type: str, csv_headers: list[str] | None = None
) -> Dict[str, str]:
    """Get field mapping for a specific file type, with auto-detection of export format.

    Args:
        file_type: Type of CSV file (e.g., 'keywords', 'search_terms').
        csv_headers: Optional list of CSV headers for format auto-detection.

    Returns:
        Dictionary mapping CSV field names to standardized names.
    """
    # Auto-detect format if headers are provided
    if csv_headers is not None:
        detected_type = detect_export_format(csv_headers, file_type)
        return FIELD_MAPPINGS.get(detected_type, FIELD_MAPPINGS["default"])

    return FIELD_MAPPINGS.get(file_type, FIELD_MAPPINGS["default"])


def get_available_file_types() -> list[str]:
    """Get list of available file type mappings.

    Returns:
        List of supported file types.
    """
    return list(FIELD_MAPPINGS.keys())


def validate_csv_headers(file_type: str, csv_headers: list[str]) -> list[str]:
    """Validate that required fields are present in CSV headers with format auto-detection.

    Args:
        file_type: Type of CSV file (e.g., 'keywords', 'search_terms').
        csv_headers: List of headers from the CSV file.

    Returns:
        List of missing required fields. Empty list if all required fields are present.
    """
    # Auto-detect the actual file format
    detected_type = detect_export_format(csv_headers, file_type)

    # Define required fields for each file type (API exports)
    api_required_fields = {
        "keywords": [
            "Keyword ID",
            "Campaign ID",
            "Campaign",
            "Ad group ID",
            "Ad group",
            "Keyword",
            "Match type",
            "Status",
        ],
        "search_terms": [
            "Campaign ID",
            "Campaign",
            "Ad group ID",
            "Ad group",
            "Search term",
        ],
        "geo_performance": [
            "Customer ID",
            "Campaign ID",
            "Campaign",
            "Location type",
            "Location",
        ],
        "campaigns": ["Campaign", "Campaign state"],
        "ad_groups": ["Campaign", "Ad group", "Ad group state"],
        "negative_keywords": ["Negative keyword", "Match type"],
        "device": ["Device", "Campaign", "Clicks", "Cost"],
        "ad_schedule": ["Day & time", "Clicks", "Cost"],
        "per_store": ["Store locations", "Local reach (impressions)"],
        "auction_insights": ["Display URL domain", "Impr. share"],
    }

    # Define required fields for UI exports (no ID fields required)
    ui_required_fields = {
        "keywords_ui": [
            "Keyword",
            "Match type",
            "Campaign",
            "Ad group",
        ],
        "search_terms_ui": [
            "Search term",
            "Match type",
            "Campaign",
            "Ad group",
        ],
        "negative_keywords_ui": [
            "Negative keyword",
            "Match type",
        ],
    }

    # Combine both requirement sets
    all_required_fields = {**api_required_fields, **ui_required_fields}

    # Get required fields for the detected type
    required = all_required_fields.get(detected_type, [])

    # Find missing fields
    missing_fields = []
    for field in required:
        if field not in csv_headers:
            missing_fields.append(field)

    return missing_fields
