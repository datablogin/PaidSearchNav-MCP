#!/usr/bin/env python3
"""
Discover Themis Legal Group account structure and permissions
This script will help identify the correct manager customer ID and account structure
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from google.ads.googleads.client import GoogleAdsClient

from paidsearchnav.core.config import Settings


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


def create_google_ads_client_with_login_customer(
    login_customer_id: Optional[str] = None,
) -> GoogleAdsClient:
    """Create Google Ads client with optional login customer ID."""

    settings = Settings.from_env()

    credentials_dict = {
        "developer_token": settings.google_ads.developer_token.get_secret_value(),
        "client_id": settings.google_ads.client_id,
        "client_secret": settings.google_ads.client_secret.get_secret_value(),
        "refresh_token": settings.google_ads.refresh_token.get_secret_value(),
        "use_proto_plus": True,
    }

    if login_customer_id:
        credentials_dict["login_customer_id"] = login_customer_id

    return GoogleAdsClient.load_from_dict(credentials_dict, version="v20")


def try_access_account(
    client: GoogleAdsClient, customer_id: str, description: str
) -> Dict[str, Any]:
    """Try to access an account and return results."""

    logger = logging.getLogger(__name__)

    try:
        ga_service = client.get_service("GoogleAdsService")

        # Simple query to test access
        query = """
        SELECT
            customer.id,
            customer.descriptive_name,
            customer.manager,
            customer.test_account,
            customer.time_zone,
            customer.currency_code
        FROM customer
        LIMIT 1
        """

        logger.info(f"🔍 Trying to access {description} (ID: {customer_id})...")

        request = client.get_type("SearchGoogleAdsRequest")
        request.customer_id = customer_id
        request.query = query

        response = ga_service.search(request=request)

        results = []
        for row in response:
            customer = row.customer
            results.append(
                {
                    "customer_id": customer.id,
                    "name": customer.descriptive_name,
                    "is_manager": customer.manager,
                    "is_test": customer.test_account,
                    "time_zone": customer.time_zone,
                    "currency": customer.currency_code,
                }
            )

        logger.info(f"✅ Successfully accessed {description}")
        return {
            "success": True,
            "customer_id": customer_id,
            "description": description,
            "results": results,
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"❌ Failed to access {description}: {error_msg}")

        return {
            "success": False,
            "customer_id": customer_id,
            "description": description,
            "error": error_msg,
        }


def find_manager_accounts(client: GoogleAdsClient) -> Dict[str, Any]:
    """Try to find accessible manager accounts."""

    logger = logging.getLogger(__name__)

    try:
        ga_service = client.get_service("GoogleAdsService")

        # Query to find manager accounts
        query = """
        SELECT
            customer_client.id,
            customer_client.descriptive_name,
            customer_client.manager,
            customer_client.level,
            customer_client.test_account
        FROM customer_client
        WHERE customer_client.manager = true
        """

        logger.info("🔍 Searching for manager accounts...")

        # Try with different potential manager IDs or no login customer
        potential_managers = [
            None,  # Try without login customer first
        ]

        for manager_id in potential_managers:
            try:
                if manager_id:
                    logger.info(f"Trying with manager ID: {manager_id}")

                request = client.get_type("SearchGoogleAdsRequest")
                request.customer_id = manager_id or "0"  # Use manager as customer
                request.query = query

                response = ga_service.search(request=request)

                results = []
                for row in response:
                    customer = row.customer_client
                    results.append(
                        {
                            "customer_id": customer.id,
                            "name": customer.descriptive_name,
                            "is_manager": customer.manager,
                            "level": customer.level,
                            "is_test": customer.test_account,
                        }
                    )

                logger.info(f"✅ Found {len(results)} manager accounts")
                return {"success": True, "results": results}

            except Exception as e:
                logger.debug(f"Manager search failed: {e}")
                continue

        return {"success": False, "error": "No accessible manager accounts found"}

    except Exception as e:
        logger.error(f"❌ Manager search failed: {e}")
        return {"success": False, "error": str(e)}


async def discover_themis_legal_structure():
    """Discover the account structure for Themis Legal Group."""

    logger = setup_logging()

    logger.info("🚀 Starting Themis Legal Group account discovery...")

    # Target account details
    themis_customer_id = "4418768623"  # 441-876-8623 formatted

    discovery_results = {
        "timestamp": datetime.now().isoformat(),
        "target_account": {
            "customer_id": themis_customer_id,
            "formatted_id": "441-876-8623",
            "name": "Themis Legal Group",
        },
        "access_attempts": [],
        "recommendations": [],
    }

    # Test 1: Try direct access (no login customer)
    logger.info("\n📋 Test 1: Direct account access (no login customer)")
    client_no_login = create_google_ads_client_with_login_customer(None)

    direct_result = try_access_account(
        client_no_login, themis_customer_id, "Themis Legal (Direct Access)"
    )
    discovery_results["access_attempts"].append(direct_result)

    if direct_result["success"]:
        logger.info("🎉 Direct access successful! No manager account needed.")
        discovery_results["recommendations"].append(
            {
                "type": "direct_access",
                "message": "Account can be accessed directly without login_customer_id",
                "implementation": 'Use customer_id = "4418768623" without login_customer_id',
            }
        )
        return discovery_results

    # Test 2: Try to find manager accounts
    logger.info("\n📋 Test 2: Searching for manager accounts")
    manager_search = find_manager_accounts(client_no_login)
    discovery_results["manager_search"] = manager_search

    if manager_search["success"] and manager_search["results"]:
        logger.info(f"🎉 Found {len(manager_search['results'])} manager accounts!")

        # Test each manager account as login customer
        for manager in manager_search["results"]:
            manager_id = str(manager["customer_id"])
            logger.info(
                f"\n📋 Test 3.{manager['customer_id']}: Using manager {manager['name']} ({manager_id})"
            )

            client_with_manager = create_google_ads_client_with_login_customer(
                manager_id
            )

            manager_result = try_access_account(
                client_with_manager,
                themis_customer_id,
                f"Themis Legal via Manager {manager['name']}",
            )

            manager_result["login_customer_id"] = manager_id
            discovery_results["access_attempts"].append(manager_result)

            if manager_result["success"]:
                logger.info(
                    f"🎉 Success! Manager {manager['name']} can access Themis Legal!"
                )
                discovery_results["recommendations"].append(
                    {
                        "type": "manager_access",
                        "message": f"Use manager account {manager['name']} ({manager_id}) as login_customer_id",
                        "implementation": f'Set login_customer_id = "{manager_id}" in client configuration',
                        "manager_details": manager,
                    }
                )

    # Test 3: Common manager account ID patterns (if no managers found)
    if not discovery_results["recommendations"]:
        logger.info("\n📋 Test 3: Trying common manager account patterns")

        # Common patterns for the account number - must be exactly 10 digits
        potential_managers = [
            "4418768620",  # Change last digit to 0
            "4418768621",  # Change last digit to 1
            "4418768622",  # Change last digit to 2
            "4418768624",  # Change last digit to 4
            "4418768625",  # Change last digit to 5
            "4418768626",  # Change last digit to 6
            "4418768627",  # Change last digit to 7
            "4418768628",  # Change last digit to 8
            "4418768629",  # Change last digit to 9
            "4418768600",  # Change last 2 digits to 00
            "4418768610",  # Change last 2 digits to 10
        ]

        for potential_manager in potential_managers:
            logger.info(f"\n📋 Trying potential manager: {potential_manager}")

            client_with_potential = create_google_ads_client_with_login_customer(
                potential_manager
            )

            potential_result = try_access_account(
                client_with_potential,
                themis_customer_id,
                f"Themis Legal via Potential Manager {potential_manager}",
            )

            potential_result["login_customer_id"] = potential_manager
            discovery_results["access_attempts"].append(potential_result)

            if potential_result["success"]:
                logger.info(
                    f"🎉 Success! Manager {potential_manager} can access Themis Legal!"
                )
                discovery_results["recommendations"].append(
                    {
                        "type": "discovered_manager",
                        "message": f"Use manager account {potential_manager} as login_customer_id",
                        "implementation": f'Set login_customer_id = "{potential_manager}" in client configuration',
                    }
                )
                break

    # Generate final recommendations
    if not discovery_results["recommendations"]:
        logger.warning("❌ No working access method found")
        discovery_results["recommendations"].append(
            {
                "type": "manual_investigation",
                "message": "Manual investigation required",
                "implementation": "Contact Google Ads support or account owner to verify account structure and permissions",
            }
        )

    return discovery_results


def generate_discovery_report(results: Dict[str, Any]) -> str:
    """Generate human-readable discovery report."""

    report = f"""# Themis Legal Group Account Discovery Report

**Generated:** {results["timestamp"]}
**Target Account:** {results["target_account"]["name"]} ({results["target_account"]["formatted_id"]})
**Customer ID:** {results["target_account"]["customer_id"]}

## Discovery Results

"""

    # Access attempts summary
    successful_attempts = [
        attempt for attempt in results["access_attempts"] if attempt["success"]
    ]
    failed_attempts = [
        attempt for attempt in results["access_attempts"] if not attempt["success"]
    ]

    report += "### Access Attempts Summary\n"
    report += f"- **Total Attempts:** {len(results['access_attempts'])}\n"
    report += f"- **Successful:** {len(successful_attempts)}\n"
    report += f"- **Failed:** {len(failed_attempts)}\n\n"

    # Successful attempts
    if successful_attempts:
        report += "### ✅ Successful Access Methods\n"
        for i, attempt in enumerate(successful_attempts, 1):
            login_customer = attempt.get("login_customer_id", "None")
            report += f"{i}. **{attempt['description']}**\n"
            report += f"   - Login Customer ID: {login_customer}\n"
            if attempt.get("results"):
                for result in attempt["results"]:
                    report += f"   - Account: {result.get('name', 'Unknown')} (Manager: {result.get('is_manager', False)})\n"
            report += "\n"

    # Failed attempts (summary)
    if failed_attempts:
        report += "### ❌ Failed Access Attempts\n"
        for i, attempt in enumerate(failed_attempts, 1):
            login_customer = attempt.get("login_customer_id", "None")
            report += (
                f"{i}. **{attempt['description']}** (Login ID: {login_customer})\n"
            )
            if "USER_PERMISSION_DENIED" in attempt.get("error", ""):
                report += (
                    "   - Error: Permission denied (needs correct manager account)\n"
                )
            else:
                report += (
                    f"   - Error: {attempt.get('error', 'Unknown error')[:100]}...\n"
                )
        report += "\n"

    # Recommendations
    report += "## 🎯 Recommendations\n\n"

    if results["recommendations"]:
        for i, rec in enumerate(results["recommendations"], 1):
            report += f"### {i}. {rec['type'].replace('_', ' ').title()}\n"
            report += f"**Message:** {rec['message']}\n\n"
            report += "**Implementation:**\n"
            report += f"```\n{rec['implementation']}\n```\n\n"

            if "manager_details" in rec:
                manager = rec["manager_details"]
                report += "**Manager Account Details:**\n"
                report += f"- ID: {manager['customer_id']}\n"
                report += f"- Name: {manager['name']}\n"
                report += f"- Level: {manager.get('level', 'Unknown')}\n\n"

    # Next steps
    report += "## 🚀 Next Steps\n\n"

    if successful_attempts:
        report += (
            "1. **Update Live Data Analysis Script** with working login_customer_id\n"
        )
        report += "2. **Run 90-Day Analysis** using discovered access method\n"
        report += "3. **Verify Data Access** for all required report types\n"
        report += "4. **Document Working Configuration** for future use\n\n"
    else:
        report += (
            "1. **Contact Account Owner** to verify Google Ads account structure\n"
        )
        report += "2. **Check MCC Permissions** - ensure developer token has access\n"
        report += "3. **Verify Customer ID Format** - confirm 441-876-8623 is correct\n"
        report += "4. **Request Access** through proper Google Ads channels\n\n"

    report += "---\n"
    report += "*Generated by PaidSearchNav Account Discovery Tool*\n"

    return report


async def main():
    """Main execution function."""
    logger = setup_logging()

    try:
        # Create output directory
        output_dir = Path("customers/themis_legal")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run discovery
        results = await discover_themis_legal_structure()

        # Generate timestamp
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON results
        import json

        json_path = output_dir / f"account_discovery_{date_str}.json"
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        # Generate and save report
        report = generate_discovery_report(results)
        report_path = output_dir / f"account_discovery_report_{date_str}.md"
        with open(report_path, "w") as f:
            f.write(report)

        logger.info("\n🎉 Account discovery completed!")
        logger.info(f"📊 JSON Results: {json_path.name}")
        logger.info(f"📋 Report: {report_path.name}")

        # Print summary
        successful_attempts = [
            attempt for attempt in results["access_attempts"] if attempt["success"]
        ]
        if successful_attempts:
            logger.info(f"✅ Found {len(successful_attempts)} working access methods!")
            for attempt in successful_attempts:
                login_id = attempt.get("login_customer_id", "None")
                logger.info(f"   - {attempt['description']} (Login ID: {login_id})")
        else:
            logger.warning("❌ No working access methods found")
            logger.info("📞 Manual investigation required - see report for details")

    except Exception as e:
        logger.error(f"❌ Account discovery failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
