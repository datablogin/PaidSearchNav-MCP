#!/bin/bash
# Package all Tier 1 skills for distribution

set -e  # Exit on error

echo "📦 Packaging all PaidSearchNav Claude Skills..."
echo ""

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Create dist directory
mkdir -p dist

# Run the Python packaging script
python scripts/package_skill.py --all --output dist

echo ""
echo "✅ All Tier 1 skills packaged in dist/"
echo ""
echo "Contents of dist/:"
ls -lh dist/ | grep -E "\.zip$" || echo "No .zip files found"
echo ""
echo "📝 Skills packaged:"
echo "   1. KeywordMatchAnalyzer"
echo "   2. SearchTermAnalyzer"
echo "   3. NegativeConflictAnalyzer"
echo "   4. GeoPerformanceAnalyzer"
echo "   5. PMaxAnalyzer"
echo ""
echo "🎯 These 5 skills form the Cost Efficiency Suite for quarterly Google Ads audits."
