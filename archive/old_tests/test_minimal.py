"""Minimal test to verify basic imports work correctly."""

import sys

print(f"Python version: {sys.version}")
print("Running minimal import tests...")

try:
    # Test core imports
    import paidsearchnav  # noqa: F401

    print("✓ paidsearchnav package imports successfully")

    # Test basic modules
    from paidsearchnav.core import config  # noqa: F401

    print("✓ paidsearchnav.core.config imports successfully")

    from paidsearchnav.services import customer_service  # noqa: F401

    print("✓ paidsearchnav.services imports successfully")

    # Test GraphQL imports
    from paidsearchnav.graphql import schema  # noqa: F401

    print("✓ paidsearchnav.graphql imports successfully")

    print("\nAll basic imports successful!")

except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)
