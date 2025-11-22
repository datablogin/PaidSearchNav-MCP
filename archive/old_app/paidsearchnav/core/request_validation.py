"""Shared validation utilities for the PaidSearchNav API."""

from email_validator import EmailNotValidError, validate_email


def validate_email_address(email: str) -> str:
    """Validate email address using email-validator library.

    Args:
        email: Email address to validate

    Returns:
        Normalized email address

    Raises:
        ValueError: If email is invalid
    """
    try:
        # Validate and normalize the email - disable deliverability check for faster validation
        validated_email = validate_email(email.strip(), check_deliverability=False)
        # Manually normalize to lowercase
        return validated_email.normalized.lower()
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email address: {str(e)}")


def validate_google_ads_customer_id(customer_id: str) -> str:
    """Validate Google Ads Customer ID format.

    Args:
        customer_id: Google Ads Customer ID to validate

    Returns:
        Cleaned customer ID (digits only)

    Raises:
        ValueError: If customer ID format is invalid
    """
    # Remove hyphens and spaces
    clean_id = customer_id.replace("-", "").replace(" ", "")

    if not clean_id.isdigit() or len(clean_id) != 10:
        raise ValueError("Google Ads Customer ID must be 10 digits")

    return clean_id


def validate_user_type(user_type: str) -> str:
    """Validate user type.

    Args:
        user_type: User type to validate

    Returns:
        Normalized user type (lowercase)

    Raises:
        ValueError: If user type is not allowed
    """
    allowed_types = ["individual", "agency"]
    normalized = user_type.lower().strip()

    if normalized not in allowed_types:
        raise ValueError(f"User type must be one of: {', '.join(allowed_types)}")

    return normalized
