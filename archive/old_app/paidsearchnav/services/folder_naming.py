"""Folder naming and validation utilities for S3 customer directories."""

import re
import uuid
from pathlib import Path
from typing import List, Set

from paidsearchnav.core.models.customer_init import BusinessType


class FolderNamingError(Exception):
    """Raised when folder naming operations fail."""

    pass


class PathValidationError(Exception):
    """Raised when path validation fails."""

    pass


# Reserved names that should not be used in S3 paths
RESERVED_NAMES: Set[str] = {
    "admin",
    "api",
    "app",
    "archive",
    "backup",
    "cache",
    "config",
    "data",
    "demo",
    "dev",
    "docs",
    "example",
    "exports",
    "files",
    "ftp",
    "images",
    "imports",
    "logs",
    "mail",
    "media",
    "private",
    "public",
    "reports",
    "root",
    "sample",
    "shared",
    "static",
    "system",
    "temp",
    "test",
    "tmp",
    "uploads",
    "user",
    "users",
    "www",
}

# AWS S3 naming restrictions
MAX_SEGMENT_LENGTH = 63  # Maximum length for a single path segment
MAX_PATH_LENGTH = 1024  # Maximum total path length


def sanitize_customer_name(name: str) -> str:
    """Sanitize customer name for use in S3 paths.

    Args:
        name: Raw customer name

    Returns:
        Sanitized name safe for S3 paths

    Raises:
        FolderNamingError: If name cannot be sanitized
    """
    if not name or not name.strip():
        raise FolderNamingError("Customer name cannot be empty")

    # Remove extra whitespace and convert to lowercase
    sanitized = name.strip().lower()

    # Replace spaces and special characters with hyphens
    # Allow only alphanumeric, hyphens, and underscores
    sanitized = re.sub(r"[^a-z0-9-_]+", "-", sanitized)

    # Remove multiple consecutive hyphens
    sanitized = re.sub(r"-+", "-", sanitized)

    # Remove leading/trailing hyphens
    sanitized = sanitized.strip("-_")

    if not sanitized:
        raise FolderNamingError("Customer name contains no valid characters")

    # Check length
    if len(sanitized) > MAX_SEGMENT_LENGTH:
        # Truncate but preserve meaningful content
        sanitized = sanitized[:MAX_SEGMENT_LENGTH].rstrip("-_")

    # Check for reserved names
    if sanitized in RESERVED_NAMES:
        sanitized = f"customer-{sanitized}"

    # Ensure it doesn't start with a number or special character
    if sanitized[0].isdigit() or sanitized[0] in "-_":
        sanitized = f"customer-{sanitized}"

    return sanitized


def generate_customer_number() -> str:
    """Generate a unique customer number for folder naming.

    Returns:
        12-character alphanumeric customer number
    """
    return str(uuid.uuid4()).replace("-", "").upper()[:12]


def generate_business_type_prefix(business_type: BusinessType) -> str:
    """Generate a prefix based on business type.

    Args:
        business_type: Type of business

    Returns:
        Short prefix for folder organization
    """
    prefixes = {
        BusinessType.RETAIL: "ret",
        BusinessType.ECOMMERCE: "ecom",
        BusinessType.SERVICE: "svc",
        BusinessType.LEGAL: "leg",
        BusinessType.SAAS: "saas",
        BusinessType.HEALTHCARE: "hlth",
        BusinessType.AUTOMOTIVE: "auto",
        BusinessType.REAL_ESTATE: "re",
        BusinessType.EDUCATION: "edu",
        BusinessType.NONPROFIT: "npo",
        BusinessType.OTHER: "misc",
    }
    return prefixes.get(business_type, "misc")


def create_folder_structure(
    customer_name: str, business_type: BusinessType, customer_number: str = None
) -> dict[str, str]:
    """Create complete folder structure for a customer.

    Args:
        customer_name: Customer name to sanitize
        business_type: Type of business
        customer_number: Optional customer number (generated if not provided)

    Returns:
        Dictionary with folder paths:
        - base_path: Root customer directory
        - inputs: Input files directory
        - outputs: Output files directory
        - reports: Reports directory
        - actionable: Actionable exports directory

    Raises:
        FolderNamingError: If folder structure cannot be created
    """
    try:
        sanitized_name = sanitize_customer_name(customer_name)
        if not customer_number:
            customer_number = generate_customer_number()

        business_prefix = generate_business_type_prefix(business_type)

        # Create base path: business_type/sanitized_name_customer_number
        base_folder = f"{sanitized_name}_{customer_number}"
        base_path = f"{business_prefix}/{base_folder}"

        # Create subdirectories
        structure = {
            "base_path": base_path,
            "customer_name_sanitized": sanitized_name,
            "customer_number": customer_number,
            "inputs_path": f"{base_path}/inputs",
            "outputs_path": f"{base_path}/outputs",
            "reports_path": f"{base_path}/reports",
            "actionable_files_path": f"{base_path}/actionable",
        }

        # Validate all paths
        for path_key, path_value in structure.items():
            if path_key != "customer_name_sanitized" and path_key != "customer_number":
                validate_s3_path(path_value)

        return structure

    except Exception as e:
        raise FolderNamingError(f"Failed to create folder structure: {str(e)}")


def validate_s3_path(path: str) -> bool:
    """Validate S3 path follows AWS naming conventions.

    Args:
        path: S3 path to validate

    Returns:
        True if path is valid

    Raises:
        PathValidationError: If path is invalid
    """
    if not path:
        raise PathValidationError("Path cannot be empty")

    # Check for consecutive slashes or other issues (do this before Path conversion)
    if "//" in path:
        raise PathValidationError("Path cannot have consecutive slashes")
    if path.startswith("/") or path.endswith("/"):
        raise PathValidationError("Path cannot start/end with slash")

    # Check total length
    if len(path) > MAX_PATH_LENGTH:
        raise PathValidationError(f"Path too long: {len(path)} > {MAX_PATH_LENGTH}")

    # Convert to Path object for validation
    path_obj = Path(path)

    # Check each path segment
    for part in path_obj.parts:
        if not part:
            raise PathValidationError("Path cannot contain empty segments")

        if len(part) > MAX_SEGMENT_LENGTH:
            raise PathValidationError(
                f"Path segment too long: '{part}' ({len(part)} > {MAX_SEGMENT_LENGTH})"
            )

        # Check for invalid characters
        if not re.match(r"^[a-zA-Z0-9._-]+$", part):
            raise PathValidationError(
                f"Path segment contains invalid characters: '{part}'"
            )

        # Check for leading/trailing periods or hyphens
        if part.startswith(".") or part.endswith("."):
            raise PathValidationError(
                f"Path segment cannot start/end with period: '{part}'"
            )

        if part.startswith("-") or part.endswith("-"):
            raise PathValidationError(
                f"Path segment cannot start/end with hyphen: '{part}'"
            )

    return True


def validate_folder_names(folder_list: List[str]) -> List[str]:
    """Validate a list of folder names.

    Args:
        folder_list: List of folder paths to validate

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []

    for i, folder_path in enumerate(folder_list):
        try:
            validate_s3_path(folder_path)
        except PathValidationError as e:
            errors.append(f"Folder {i + 1} '{folder_path}': {str(e)}")

    return errors


def get_customer_base_path(customer_name: str, business_type: BusinessType) -> str:
    """Get the base S3 path for a customer without creating full structure.

    Args:
        customer_name: Customer name
        business_type: Business type

    Returns:
        Base S3 path for the customer
    """
    sanitized_name = sanitize_customer_name(customer_name)
    business_prefix = generate_business_type_prefix(business_type)
    customer_number = generate_customer_number()

    base_folder = f"{sanitized_name}_{customer_number}"
    return f"{business_prefix}/{base_folder}"


def extract_customer_info_from_path(s3_path: str) -> dict[str, str]:
    """Extract customer information from an S3 path.

    Args:
        s3_path: S3 path to parse

    Returns:
        Dictionary with extracted info:
        - business_type_prefix: Business type prefix
        - customer_name: Sanitized customer name
        - customer_number: Customer number

    Raises:
        PathValidationError: If path format is invalid
    """
    if not s3_path:
        raise PathValidationError("Path cannot be empty")

    path_parts = s3_path.strip("/").split("/")

    if len(path_parts) < 2:
        raise PathValidationError(
            "Path must have at least business_type/customer format"
        )

    business_prefix = path_parts[0]
    customer_folder = path_parts[1]

    # Parse customer folder: name_number format
    if "_" not in customer_folder:
        raise PathValidationError("Customer folder must be in format: name_number")

    # Split on last underscore to handle names with underscores
    parts = customer_folder.rsplit("_", 1)
    if len(parts) != 2:
        raise PathValidationError("Invalid customer folder format")

    customer_name, customer_number = parts

    if not customer_name or not customer_number:
        raise PathValidationError("Customer name and number cannot be empty")

    # Validate customer number format (should be alphanumeric and reasonable length)
    if (
        not customer_number.isalnum()
        or len(customer_number) < 8
        or len(customer_number) > 20
    ):
        raise PathValidationError(
            "Customer number must be 8-20 alphanumeric characters"
        )

    return {
        "business_type_prefix": business_prefix,
        "customer_name": customer_name,
        "customer_number": customer_number,
    }


def is_valid_customer_path(s3_path: str) -> bool:
    """Check if an S3 path represents a valid customer directory.

    Args:
        s3_path: S3 path to check

    Returns:
        True if path is a valid customer directory
    """
    try:
        validate_s3_path(s3_path)
        extract_customer_info_from_path(s3_path)
        return True
    except (PathValidationError, FolderNamingError):
        return False
