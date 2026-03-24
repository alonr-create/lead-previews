#!/bin/bash
# Deploy lead previews to GitHub + Vercel
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
REPO_NAME="lead-previews"
GH_USER="alonr-create"

echo "=== Lead Previews Deploy ==="

# Check output exists
if [ ! -d "$OUTPUT_DIR" ] || [ ! -f "$OUTPUT_DIR/index.html" ]; then
  echo "Error: output/ directory not found. Run generate.py first."
  exit 1
fi

cd "$OUTPUT_DIR"

# Init git if needed
if [ ! -d ".git" ]; then
  git init
  git branch -M main
fi

# Create GitHub repo if it doesn't exist
if ! gh repo view "$GH_USER/$REPO_NAME" >/dev/null 2>&1; then
  echo "Creating GitHub repo $GH_USER/$REPO_NAME..."
  gh repo create "$GH_USER/$REPO_NAME" --public --description "Personalized website previews for lead outreach"
fi

# Set remote
REMOTE_URL="https://github.com/$GH_USER/$REPO_NAME.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

# Add, commit, push
git add -A
git commit -m "Update lead previews $(date +%Y-%m-%d)" || echo "Nothing to commit"
git push -u origin main --force

echo ""
echo "=== Deployed ==="
echo "GitHub: https://github.com/$GH_USER/$REPO_NAME"
echo "Vercel will auto-deploy. Base URL:"
echo "  https://$REPO_NAME.vercel.app"
echo ""
echo "Example preview URL:"
echo "  https://$REPO_NAME.vercel.app/{business-slug}/"
