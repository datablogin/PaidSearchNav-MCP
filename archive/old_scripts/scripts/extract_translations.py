#!/usr/bin/env python
"""Extract translatable strings from the codebase and create/update .pot files."""

import os
import subprocess
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
TRANSLATIONS_DIR = PROJECT_ROOT / "translations"
SOURCE_DIR = PROJECT_ROOT / "paidsearchnav"


def extract_python_strings():
    """Extract translatable strings from Python files."""
    print("Extracting translatable strings from Python files...")

    # Create translations directory if it doesn't exist
    TRANSLATIONS_DIR.mkdir(exist_ok=True)

    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    if not python_files:
        print("No Python files found!")
        return

    # Create POT file using xgettext
    pot_file = TRANSLATIONS_DIR / "paidsearchnav.pot"

    cmd = [
        "xgettext",
        "--language=Python",
        "--keyword=_",
        "--keyword=_n:1,2",
        "--keyword=_lazy",
        "--keyword=gettext",
        "--keyword=ngettext:1,2",
        "--keyword=lazy_gettext",
        "--from-code=UTF-8",
        "--add-comments=Translators:",
        "--package-name=PaidSearchNav",
        "--package-version=1.0",
        "--msgid-bugs-address=support@paidsearchnav.com",
        f"--output={pot_file}",
    ] + python_files

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully created {pot_file}")
        else:
            print(f"Error creating POT file: {result.stderr}")
            return
    except FileNotFoundError:
        print("ERROR: xgettext not found. Please install gettext tools:")
        print("  Ubuntu/Debian: sudo apt-get install gettext")
        print("  macOS: brew install gettext && brew link gettext --force")
        print(
            "  Windows: Download from https://mlocati.github.io/articles/gettext-iconv-windows.html"
        )
        return


def update_po_files():
    """Update existing .po files with new strings from .pot file."""
    pot_file = TRANSLATIONS_DIR / "paidsearchnav.pot"

    if not pot_file.exists():
        print("POT file not found. Run extract_python_strings() first.")
        return

    # List of supported languages
    languages = ["en_US", "es_ES", "fr_FR", "de_DE", "ja_JP", "pt_BR"]

    for lang in languages:
        lang_dir = TRANSLATIONS_DIR / lang / "LC_MESSAGES"
        lang_dir.mkdir(parents=True, exist_ok=True)

        po_file = lang_dir / "paidsearchnav.po"

        if po_file.exists():
            # Update existing PO file
            print(f"Updating {lang} translations...")
            cmd = [
                "msgmerge",
                "--update",
                "--no-fuzzy-matching",
                "--backup=off",
                str(po_file),
                str(pot_file),
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"  Updated {po_file}")
                else:
                    print(f"  Error updating {po_file}: {result.stderr}")
            except FileNotFoundError:
                print("ERROR: msgmerge not found. Please install gettext tools.")
                return
        else:
            # Create new PO file
            print(f"Creating {lang} translation file...")
            cmd = [
                "msginit",
                f"--input={pot_file}",
                f"--output={po_file}",
                f"--locale={lang}",
                "--no-translator",
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"  Created {po_file}")
                else:
                    print(f"  Error creating {po_file}: {result.stderr}")
            except FileNotFoundError:
                print("ERROR: msginit not found. Please install gettext tools.")
                return


def compile_translations():
    """Compile .po files to .mo files for use by the application."""
    print("\nCompiling translations...")

    # List of supported languages
    languages = ["en_US", "es_ES", "fr_FR", "de_DE", "ja_JP", "pt_BR"]

    for lang in languages:
        po_file = TRANSLATIONS_DIR / lang / "LC_MESSAGES" / "paidsearchnav.po"
        mo_file = TRANSLATIONS_DIR / lang / "LC_MESSAGES" / "paidsearchnav.mo"

        if not po_file.exists():
            print(f"  Skipping {lang}: PO file not found")
            continue

        cmd = [
            "msgfmt",
            "-o",
            str(mo_file),
            str(po_file),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  Compiled {lang} translations")
            else:
                print(f"  Error compiling {lang}: {result.stderr}")
        except FileNotFoundError:
            print("ERROR: msgfmt not found. Please install gettext tools.")
            return


def main():
    """Main function to extract and update translations."""
    print("PaidSearchNav Translation Extraction Tool")
    print("=" * 40)

    # Extract strings from Python files
    extract_python_strings()

    # Update PO files
    print("\nUpdating translation files...")
    update_po_files()

    # Compile translations
    compile_translations()

    print("\nTranslation extraction complete!")
    print("\nNext steps:")
    print("1. Send .po files to translators")
    print("2. Once translated, run this script again to compile .mo files")
    print("3. Test translations in the application")


if __name__ == "__main__":
    main()
