"""Authentication utilities for testing."""

import secrets
import string
from typing import Dict, Optional


def generate_test_token(length: int = 32) -> str:
    """Generate a secure random test token.

    Args:
        length: Length of the token to generate

    Returns:
        Cryptographically secure random token
    """
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_auth_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Create authorization headers for testing.

    Args:
        token: Optional token to use, generates secure token if not provided

    Returns:
        Authorization headers dictionary
    """
    if token is None:
        token = generate_test_token()

    return {"Authorization": f"Bearer {token}"}


def create_test_jwt_token() -> str:
    """Create a test JWT-style token.

    Returns:
        JWT-style test token (not a real JWT, just for testing)
    """
    # Generate parts that look like JWT structure but are just random
    header = generate_test_token(16)
    payload = generate_test_token(32)
    signature = generate_test_token(16)
    return f"{header}.{payload}.{signature}"
