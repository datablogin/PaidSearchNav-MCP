#!/usr/bin/env python3
"""
CLI tool for running Google Ads conflict detection analysis.

This script provides a command-line interface for the automated conflict detection system,
allowing users to run analysis, generate reports, and create bulk resolution actions.

Usage:
    python run_conflict_detection.py --customer-id 1234567890
    python run_conflict_detection.py --customer-id 1234567890 --generate-bulk-actions
    python run_conflict_detection.py --customer-id 1234567890 --history-days 30

Based on PaidSearchNav Issue #464
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from paidsearchnav.scripts.conflict_detection import (  # noqa: E402
    ConflictDetectionConfig,
    create_conflict_detection_manager,
)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("conflict_detection.log", mode="a"),
        ],
    )


async def run_conflict_analysis(
    customer_id: str,
    config: ConflictDetectionConfig,
    generate_bulk_actions: bool = False,
    output_file: Optional[str] = None,
) -> None:
    """Run conflict detection analysis for a customer.

    Args:
        customer_id: Google Ads customer ID
        config: Conflict detection configuration
        generate_bulk_actions: Whether to generate bulk resolution actions
        output_file: Optional output file for results
    """
    logger = logging.getLogger(__name__)

    try:
        print(f"🔍 Starting conflict detection analysis for customer {customer_id}")
        print("=" * 70)

        # Create manager and run analysis
        manager = create_conflict_detection_manager(customer_id, config)
        results = await manager.run_conflict_detection(customer_id)

        # Display summary
        print("\n📊 Conflict Detection Summary")
        print(f"   Account ID: {results.account_id}")
        print(f"   Analysis Time: {results.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Total Conflicts: {results.total_conflicts}")
        print(f"   High Severity: {results.high_severity_count}")
        print(f"   Estimated Monthly Loss: ${results.estimated_monthly_loss:,.2f}")

        # Detailed breakdown
        print("\n🔍 Conflict Breakdown:")
        print(
            f"   • Positive/Negative Conflicts: {len(results.positive_negative_conflicts)}"
        )
        print(f"   • Cross-Campaign Conflicts: {len(results.cross_campaign_conflicts)}")
        print(f"   • Functionality Issues: {len(results.functionality_issues)}")
        print(f"   • Geographic Conflicts: {len(results.geographic_conflicts)}")

        # Show high-severity conflicts
        if results.high_severity_count > 0:
            print("\n🚨 High-Severity Conflicts:")

            high_severity_conflicts = []
            high_severity_conflicts.extend(
                [c for c in results.positive_negative_conflicts if c.severity == "HIGH"]
            )
            high_severity_conflicts.extend(
                [c for c in results.cross_campaign_conflicts if c.severity == "HIGH"]
            )
            high_severity_conflicts.extend(
                [c for c in results.functionality_issues if c.severity == "HIGH"]
            )
            high_severity_conflicts.extend(
                [c for c in results.geographic_conflicts if c.severity == "HIGH"]
            )

            for i, conflict in enumerate(
                high_severity_conflicts[:10], 1
            ):  # Show top 10
                print(f"   {i}. {conflict.type} - {conflict.issue}")
                print(f"      Campaign: {conflict.campaign}")
                if conflict.keyword:
                    print(f"      Keyword: {conflict.keyword}")
                if conflict.estimated_impact:
                    if "wastedSpend" in conflict.estimated_impact:
                        print(
                            f"      Estimated Impact: ${conflict.estimated_impact['wastedSpend']:.2f}"
                        )
                print()

        # Generate bulk actions if requested
        if generate_bulk_actions and results.total_conflicts > 0:
            print("📤 Generating bulk resolution actions...")

            bulk_actions = await manager.generate_bulk_resolution_actions(
                results=results,
                priority_filter="HIGH",  # Focus on high-priority conflicts
            )

            if bulk_actions:
                print(f"   Generated {len(bulk_actions)} bulk action files:")
                for filename in bulk_actions.keys():
                    print(f"   • {filename}")

                # Save locally if output directory specified
                if output_file:
                    output_dir = Path(output_file).parent
                    output_dir.mkdir(exist_ok=True)

                    for filename, content in bulk_actions.items():
                        file_path = output_dir / filename
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"   Saved: {file_path}")
            else:
                print("   No bulk actions generated (no actionable conflicts found)")

        # Save results to file if specified
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(results.model_dump_json(indent=2))

            print(f"\n💾 Results saved to: {output_path}")

        # Provide next steps
        print("\n📋 Recommended Next Steps:")
        if results.high_severity_count > 0:
            print("   1. Review high-severity conflicts immediately")
            print("   2. Implement bulk actions for quick resolution")
            print("   3. Monitor performance impact after changes")
        elif results.total_conflicts > 0:
            print(
                "   1. Review medium-severity conflicts for optimization opportunities"
            )
            print("   2. Consider implementing bulk actions during maintenance windows")
        else:
            print("   1. Great! No conflicts detected - account is well-optimized")
            print("   2. Schedule regular conflict detection runs to maintain quality")

        print("\n✅ Conflict detection analysis completed successfully!")

    except Exception as e:
        logger.error(f"Conflict detection analysis failed: {e}")
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1)


async def show_conflict_history(
    customer_id: str, config: ConflictDetectionConfig, days_back: int = 30
) -> None:
    """Show historical conflict detection results.

    Args:
        customer_id: Google Ads customer ID
        config: Conflict detection configuration
        days_back: Number of days of history to show
    """
    logger = logging.getLogger(__name__)

    try:
        print(
            f"📈 Retrieving conflict history for customer {customer_id} ({days_back} days)"
        )
        print("=" * 70)

        # Create manager and get history
        manager = create_conflict_detection_manager(customer_id, config)
        history = await manager.get_conflict_history(customer_id, days_back)

        if not history:
            print("No historical data found for the specified period.")
            return

        print(f"Found {len(history)} historical analysis results:\n")

        for i, result in enumerate(history, 1):
            print(f"{i}. {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Total Conflicts: {result.total_conflicts}")
            print(f"   High Severity: {result.high_severity_count}")
            print(f"   Estimated Loss: ${result.estimated_monthly_loss:,.2f}")
            print()

        # Show trend analysis
        if len(history) > 1:
            latest = history[0]
            previous = history[1]

            conflict_trend = latest.total_conflicts - previous.total_conflicts
            severity_trend = latest.high_severity_count - previous.high_severity_count
            loss_trend = latest.estimated_monthly_loss - previous.estimated_monthly_loss

            print("📊 Trend Analysis (vs previous analysis):")
            print(f"   Total Conflicts: {conflict_trend:+d}")
            print(f"   High Severity: {severity_trend:+d}")
            print(f"   Estimated Loss: ${loss_trend:+.2f}")

            if conflict_trend < 0:
                print("   🎉 Conflicts are decreasing - good optimization work!")
            elif conflict_trend > 0:
                print("   ⚠️ Conflicts are increasing - may need attention")
            else:
                print("   📊 Conflict levels are stable")

    except Exception as e:
        logger.error(f"History retrieval failed: {e}")
        print(f"\n❌ History retrieval failed: {e}")
        sys.exit(1)


def load_configuration(config_file: Optional[str] = None) -> ConflictDetectionConfig:
    """Load configuration from file or use defaults.

    Args:
        config_file: Optional path to configuration file

    Returns:
        Loaded configuration
    """
    if config_file and Path(config_file).exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            return ConflictDetectionConfig(**config_data)

        except Exception as e:
            print(f"Warning: Failed to load config file {config_file}: {e}")
            print("Using default configuration.")

    # Use default configuration
    return ConflictDetectionConfig()


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Google Ads Automated Conflict Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run conflict detection for a customer
  python run_conflict_detection.py --customer-id 1234567890

  # Generate bulk resolution actions
  python run_conflict_detection.py --customer-id 1234567890 --generate-bulk-actions

  # Save results to file
  python run_conflict_detection.py --customer-id 1234567890 --output results.json

  # View conflict history
  python run_conflict_detection.py --customer-id 1234567890 --history --days 30

  # Use custom configuration
  python run_conflict_detection.py --customer-id 1234567890 --config config.json
        """,
    )

    parser.add_argument(
        "--customer-id", required=True, help="Google Ads customer ID (without dashes)"
    )

    parser.add_argument(
        "--generate-bulk-actions",
        action="store_true",
        help="Generate bulk action CSV files for conflict resolution",
    )

    parser.add_argument("--output", help="Output file path for results (JSON format)")

    parser.add_argument("--config", help="Configuration file path (JSON format)")

    parser.add_argument(
        "--history",
        action="store_true",
        help="Show historical conflict detection results instead of running new analysis",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of history to retrieve (default: 30)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)

    # Load environment variables
    env_files = [".env.dev", ".env"]
    for env_file in env_files:
        env_path = project_root / env_file
        if env_path.exists():
            load_dotenv(env_path)
            break

    # Load configuration
    config = load_configuration(args.config)

    # Validate customer ID
    try:
        customer_id = str(int(args.customer_id.replace("-", "")))
    except ValueError:
        print(f"Error: Invalid customer ID format: {args.customer_id}")
        print("Customer ID should be numeric (e.g., 1234567890)")
        sys.exit(1)

    # Run the appropriate command
    try:
        if args.history:
            asyncio.run(show_conflict_history(customer_id, config, args.days))
        else:
            asyncio.run(
                run_conflict_analysis(
                    customer_id=customer_id,
                    config=config,
                    generate_bulk_actions=args.generate_bulk_actions,
                    output_file=args.output,
                )
            )

    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
