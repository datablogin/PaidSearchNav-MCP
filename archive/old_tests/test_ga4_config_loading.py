#!/usr/bin/env python3
"""
Test GA4 Configuration Loading
==============================

Test that GA4 configurations load properly from client JSON files.
"""

import json
from pathlib import Path

from paidsearchnav.core.config import Settings


def test_client_ga4_config_loading():
    """Test loading GA4 configs from client JSON files."""

    print("🧪 Testing GA4 Configuration Loading")
    print("=" * 50)

    clients = ["topgolf", "fitness-connection"]

    for client_name in clients:
        print(f"\n📊 Testing {client_name.title()}...")

        config_path = Path(f"configs/{client_name}.json")
        if not config_path.exists():
            print(f"  ❌ Config file not found: {config_path}")
            continue

        try:
            # Load client config
            with open(config_path) as f:
                client_config = json.load(f)

            # Test the merge process
            base_config = {}
            merged_config = Settings._merge_client_config(base_config, client_config)

            print("  ✅ Config loading: SUCCESS")

            # Check GA4 section
            if "ga4" in merged_config:
                ga4_config = merged_config["ga4"]
                print(f"  ✅ GA4 enabled: {ga4_config.get('enabled', False)}")
                print(f"  ✅ Property ID: {ga4_config.get('property_id', 'Not set')}")
                print(
                    f"  ✅ Rate limit: {ga4_config.get('requests_per_minute', 0)}/min"
                )
            else:
                print("  ⚠️  No GA4 configuration found in merged config")

        except Exception as e:
            print(f"  ❌ Config loading failed: {e}")
            return False

    print("\n🎉 GA4 Configuration Loading Test Complete!")
    return True


if __name__ == "__main__":
    test_client_ga4_config_loading()
