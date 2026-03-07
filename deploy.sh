#!/usr/bin/env bash
# deploy.sh — Prepare the site/ directory for GitHub Pages deployment
#
# This script copies the latest JSON data from output/ into site/data/
# so that the static site can be served without symlinks (which don't
# work on GitHub Pages).
#
# Usage:
#   ./deploy.sh              # Copy data and show status
#   ./deploy.sh --serve      # Copy data and start local dev server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$SCRIPT_DIR/site"
OUTPUT_DIR="$SCRIPT_DIR/output"
DATA_DIR="$SITE_DIR/data"

echo "═══════════════════════════════════════════"
echo "MassieMoney — Deploy Prep"
echo "═══════════════════════════════════════════"

# Check that output/ has JSON files
if [ ! -d "$OUTPUT_DIR" ] || [ -z "$(ls "$OUTPUT_DIR"/*.json 2>/dev/null)" ]; then
    echo "ERROR: No JSON files found in output/"
    echo "Run the pipeline first:  cd src && python run.py"
    exit 1
fi

# Remove symlink if it exists, create real directory
if [ -L "$DATA_DIR" ]; then
    echo "Removing symlink: site/data -> $(readlink "$DATA_DIR")"
    rm "$DATA_DIR"
fi

mkdir -p "$DATA_DIR"

# Copy all JSON files
echo "Copying JSON data files..."
cp "$OUTPUT_DIR"/*.json "$DATA_DIR/"

FILE_COUNT=$(ls "$DATA_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$DATA_DIR" | cut -f1)
echo "  ✓ $FILE_COUNT files copied ($TOTAL_SIZE)"
echo ""

# List files
for f in "$DATA_DIR"/*.json; do
    SIZE=$(du -h "$f" | cut -f1)
    echo "  $SIZE  $(basename "$f")"
done

echo ""
echo "═══════════════════════════════════════════"
echo "Site is ready in: site/"
echo ""
echo "To test locally:"
echo "  cd site && python3 -m http.server 8080"
echo ""
echo "To deploy to GitHub Pages:"
echo "  git add site/data/ && git commit -m 'Update data' && git push"
echo "  Then enable GitHub Pages in repo Settings → Pages → Source: GitHub Actions"
echo "═══════════════════════════════════════════"

if [ "${1:-}" = "--serve" ]; then
    echo ""
    echo "Starting local server at http://localhost:8080 ..."
    cd "$SITE_DIR"
    python3 -m http.server 8080
fi
