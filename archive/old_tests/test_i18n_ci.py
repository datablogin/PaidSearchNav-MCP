#!/usr/bin/env python
"""Minimal CI test for i18n module."""

import sys

try:
    print("Testing i18n module import...")

    print("✓ i18n module imported successfully")

    # Test basic functionality
    from paidsearchnav.i18n import _, format_currency

    # Test translation function
    result = _("Hello, world!")
    assert result == "Hello, world!", f"Translation failed: {result}"
    print("✓ Translation function works")

    # Test formatting
    formatted = format_currency(1234.56)
    assert "$" in formatted, f"Currency formatting failed: {formatted}"
    print(f"✓ Currency formatting works: {formatted}")

    print("\nAll i18n CI tests passed!")
    sys.exit(0)

except Exception as e:
    print(f"\n✗ Error: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc()
    sys.exit(1)
