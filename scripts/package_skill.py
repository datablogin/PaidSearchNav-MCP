#!/usr/bin/env python3
"""
Package a PaidSearchNav skill into a distributable .zip file.

Usage:
    python scripts/package_skill.py keyword_match_analyzer
    python scripts/package_skill.py keyword_match_analyzer --output custom_dist/
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path


def validate_skill_structure(skill_dir: Path) -> tuple[bool, list[str]]:
    """
    Validate that a skill directory has all required files.

    Args:
        skill_dir: Path to skill directory

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check if directory exists
    if not skill_dir.exists():
        errors.append(f"Skill directory not found: {skill_dir}")
        return False, errors

    if not skill_dir.is_dir():
        errors.append(f"Path is not a directory: {skill_dir}")
        return False, errors

    # Required files
    required_files = ["skill.json", "prompt.md", "README.md"]

    for filename in required_files:
        file_path = skill_dir / filename
        if not file_path.exists():
            errors.append(f"Missing required file: {filename}")

    # Validate skill.json structure
    skill_json_path = skill_dir / "skill.json"
    if skill_json_path.exists():
        try:
            with open(skill_json_path) as f:
                metadata = json.load(f)

            # Check required fields
            required_fields = [
                "name",
                "version",
                "description",
                "author",
                "category",
                "requires_mcp_tools",
                "output_format",
            ]

            for field in required_fields:
                if field not in metadata:
                    errors.append(f"skill.json missing required field: {field}")

            # Validate version format (semver: X.Y.Z)
            import re
            version = metadata.get("version", "")
            if not re.match(r"^\d+\.\d+\.\d+$", version):
                errors.append(
                    f"Invalid version format: '{version}' (expected X.Y.Z, e.g., 1.0.0)"
                )

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in skill.json: {e}")
        except Exception as e:
            errors.append(f"Error validating skill.json: {e}")

    return len(errors) == 0, errors


def package_skill(skill_name: str, output_dir: Path = Path("dist")) -> Path:
    """
    Package a skill into a distributable .zip file.

    Args:
        skill_name: Name of skill directory in skills/
        output_dir: Where to save .zip file

    Returns:
        Path to created .zip file

    Raises:
        ValueError: If skill structure is invalid
        FileNotFoundError: If skill directory doesn't exist
    """
    skill_dir = Path("skills") / skill_name

    # Validate skill structure
    is_valid, errors = validate_skill_structure(skill_dir)
    if not is_valid:
        error_msg = "Invalid skill structure:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    # Load metadata
    with open(skill_dir / "skill.json") as f:
        metadata = json.load(f)

    skill_name_from_json = metadata["name"]
    version = metadata["version"]

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create zip filename
    zip_filename = f"{skill_name_from_json}_v{version}.zip"
    zip_path = output_dir / zip_filename

    # Package skill files
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add all files from skill directory
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                # Create archive path relative to skills/ directory
                # This preserves the skill directory name in the archive
                arcname = file_path.relative_to(Path("skills"))
                zf.write(file_path, arcname)

                # Also add a LICENSE file if it exists in root
                license_path = Path("LICENSE")
                if license_path.exists():
                    zf.write(license_path, f"{skill_name}/LICENSE")

    return zip_path


def package_all_skills(output_dir: Path = Path("dist")) -> list[Path]:
    """
    Package all skills in the skills/ directory.

    Args:
        output_dir: Where to save .zip files

    Returns:
        List of paths to created .zip files
    """
    skills_dir = Path("skills")

    if not skills_dir.exists():
        print(f"Error: Skills directory not found: {skills_dir}")
        return []

    # Find all skill directories (those with skill.json)
    skill_dirs = [
        d for d in skills_dir.iterdir() if d.is_dir() and (d / "skill.json").exists()
    ]

    if not skill_dirs:
        print(f"No skills found in {skills_dir}")
        return []

    packaged_skills = []
    errors = []

    for skill_dir in skill_dirs:
        skill_name = skill_dir.name
        try:
            print(f"Packaging {skill_name}...")
            zip_path = package_skill(skill_name, output_dir)
            packaged_skills.append(zip_path)
            print(f"  ✅ Created: {zip_path}")
        except Exception as e:
            errors.append((skill_name, str(e)))
            print(f"  ❌ Failed: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Packaged {len(packaged_skills)} of {len(skill_dirs)} skills")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for skill_name, error in errors:
            print(f"  - {skill_name}: {error}")

    return packaged_skills


def main():
    """Main entry point for the packaging script."""
    parser = argparse.ArgumentParser(
        description="Package PaidSearchNav skills for distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Package single skill
  python scripts/package_skill.py keyword_match_analyzer

  # Package all skills
  python scripts/package_skill.py --all

  # Custom output directory
  python scripts/package_skill.py keyword_match_analyzer --output custom_dist/

  # Validate without packaging
  python scripts/package_skill.py keyword_match_analyzer --validate-only
        """,
    )

    parser.add_argument(
        "skill_name",
        nargs="?",
        help="Name of the skill directory to package (e.g., keyword_match_analyzer)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Package all skills in skills/ directory",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("dist"),
        help="Output directory for .zip files (default: dist/)",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate skill structure, don't create .zip",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.skill_name:
        parser.error("Either provide a skill_name or use --all")

    if args.all and args.skill_name:
        parser.error("Cannot use --all with a specific skill_name")

    try:
        if args.all:
            # Package all skills
            if args.validate_only:
                print("Validation mode not supported with --all")
                sys.exit(1)

            packaged = package_all_skills(args.output)

            if packaged:
                print(f"\n✅ Successfully packaged {len(packaged)} skill(s)")
                sys.exit(0)
            else:
                print("\n❌ No skills were packaged")
                sys.exit(1)

        else:
            # Package single skill
            skill_dir = Path("skills") / args.skill_name

            # Validate
            is_valid, errors = validate_skill_structure(skill_dir)

            if not is_valid:
                print(f"❌ Validation failed for '{args.skill_name}':")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)

            if args.validate_only:
                print(f"✅ Skill '{args.skill_name}' is valid")
                sys.exit(0)

            # Package
            zip_path = package_skill(args.skill_name, args.output)

            # Get metadata for summary
            with open(skill_dir / "skill.json") as f:
                metadata = json.load(f)

            print("\n" + "=" * 60)
            print("✅ Successfully packaged skill")
            print("=" * 60)
            print(f"Name:        {metadata['name']}")
            print(f"Version:     {metadata['version']}")
            print(f"Description: {metadata['description']}")
            print(f"Category:    {metadata['category']}")
            print(f"Output:      {zip_path}")
            print(f"Size:        {zip_path.stat().st_size:,} bytes")
            print("=" * 60)

            sys.exit(0)

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n❌ File not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
