"""S3 path utilities for consistent path generation.

This module provides utilities for generating standardized S3 paths
for customer data storage and analysis results.

S3 Path Conventions:
-------------------
- Customer base path: s3://paidsearchnav-data/{customer_id}/
- Google Ads account path: s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}/
- Analysis input: s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}/input/{date}/
- Analysis output: s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}/output/{date}/{analysis_type}/
- Audit results: s3://paidsearchnav-data/{customer_id}/audits/{audit_id}/
"""

from datetime import datetime
from typing import Optional

S3_BUCKET_BASE = "s3://paidsearchnav-data"


def get_customer_base_path(customer_id: str) -> str:
    """Get the base S3 path for a customer.

    Args:
        customer_id: The customer's UUID

    Returns:
        S3 path like: s3://paidsearchnav-data/{customer_id}
    """
    if not customer_id:
        raise ValueError("Customer ID cannot be empty")
    return f"{S3_BUCKET_BASE}/{customer_id}"


def get_google_ads_account_path(customer_id: str, google_ads_customer_id: str) -> str:
    """Get the S3 path for a specific Google Ads account.

    Args:
        customer_id: The customer's UUID
        google_ads_customer_id: The Google Ads customer ID (7-10 digits)

    Returns:
        S3 path like: s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}
    """
    if not customer_id or not google_ads_customer_id:
        raise ValueError("Customer ID and Google Ads customer ID cannot be empty")
    return f"{get_customer_base_path(customer_id)}/{google_ads_customer_id}"


def get_analysis_input_path(
    customer_id: str, google_ads_customer_id: str, date: Optional[datetime] = None
) -> str:
    """Get the S3 path for analysis input data.

    Args:
        customer_id: The customer's UUID
        google_ads_customer_id: The Google Ads customer ID
        date: Optional date for the input data (defaults to today)

    Returns:
        S3 path like: s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}/input/{date}
    """
    if date is None:
        date = datetime.utcnow()

    date_str = date.strftime("%Y%m%d")
    base_path = get_google_ads_account_path(customer_id, google_ads_customer_id)
    return f"{base_path}/input/{date_str}"


def get_analysis_output_path(
    customer_id: str,
    google_ads_customer_id: str,
    analysis_type: str,
    date: Optional[datetime] = None,
) -> str:
    """Get the S3 path for analysis output/results.

    Args:
        customer_id: The customer's UUID
        google_ads_customer_id: The Google Ads customer ID
        analysis_type: Type of analysis (e.g., 'search_terms', 'negative_conflicts')
        date: Optional date for the output data (defaults to today)

    Returns:
        S3 path like: s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}/output/{date}/{analysis_type}
    """
    if not analysis_type:
        raise ValueError("Analysis type cannot be empty")

    if date is None:
        date = datetime.utcnow()

    date_str = date.strftime("%Y%m%d")
    base_path = get_google_ads_account_path(customer_id, google_ads_customer_id)
    return f"{base_path}/output/{date_str}/{analysis_type}"


def get_audit_results_path(customer_id: str, audit_id: str) -> str:
    """Get the S3 path for audit results.

    Args:
        customer_id: The customer's UUID
        audit_id: The audit's UUID

    Returns:
        S3 path like: s3://paidsearchnav-data/{customer_id}/audits/{audit_id}
    """
    if not audit_id:
        raise ValueError("Audit ID cannot be empty")

    base_path = get_customer_base_path(customer_id)
    return f"{base_path}/audits/{audit_id}"


def validate_s3_path(path: str) -> bool:
    """Validate an S3 path for security.

    Args:
        path: The S3 path to validate

    Returns:
        True if the path is valid and secure

    Raises:
        ValueError: If the path is invalid or contains security issues
    """
    if not path:
        raise ValueError("S3 path cannot be empty")

    if not path.startswith("s3://"):
        raise ValueError("S3 path must start with 's3://'")

    if ".." in path:
        raise ValueError("S3 path cannot contain '..' for security reasons")

    # Check for other potentially dangerous patterns
    # Skip the initial s3:// when checking for double slashes
    path_after_protocol = path[5:]  # Skip "s3://"

    if "//" in path_after_protocol:
        raise ValueError("S3 path cannot contain '//' after the protocol")

    dangerous_patterns = ["\\", "|", "&", ";", "$", "`", "(", ")", "<", ">"]
    for pattern in dangerous_patterns:
        if pattern in path:
            raise ValueError(f"S3 path cannot contain '{pattern}' for security reasons")

    return True
