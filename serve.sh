#!/bin/bash
# Quick local dev server for MassieMoney frontend.
# Serves site/ directory on localhost:8080.
# The site/data symlink points to output/ where the JSON lives.

cd "$(dirname "$0")/site"
echo "Serving MassieMoney at http://localhost:8080"
echo "Press Ctrl+C to stop."
python3 -m http.server 8080
