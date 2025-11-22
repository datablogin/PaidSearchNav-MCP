"""Match type normalization for Google Ads exports."""

# Map Google Ads export match types to expected enum values
MATCH_TYPE_MAPPING = {
    # Exact match variations
    "Exact match": "EXACT",
    "Exact match (close variant)": "EXACT",
    "Exact": "EXACT",
    # Phrase match variations
    "Phrase match": "PHRASE",
    "Phrase match (close variant)": "PHRASE",
    "Phrase": "PHRASE",
    # Broad match variations
    "Broad match": "BROAD",
    "Broad match (close variant)": "BROAD",
    "Broad": "BROAD",
    "Broad match modifier": "BROAD",
    # Unknown/other
    "Unknown": "UNKNOWN",
    "": "UNKNOWN",
    None: "UNKNOWN",
}


def normalize_match_type(match_type: str) -> str:
    """Normalize match type from Google Ads export to expected enum value."""
    return MATCH_TYPE_MAPPING.get(match_type, "UNKNOWN")
