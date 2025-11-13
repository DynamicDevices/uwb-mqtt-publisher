#!/bin/bash
#
# Setup script to install git pre-commit hook
#

set -e

HOOK_SOURCE=".github/hooks/pre-commit.example"
HOOK_DEST=".git/hooks/pre-commit"

if [ ! -f "$HOOK_SOURCE" ]; then
    echo "Error: $HOOK_SOURCE not found!"
    exit 1
fi

# Copy the hook
cp "$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

echo "✅ Git pre-commit hook installed successfully!"
echo ""
echo "The hook will automatically run flake8 on staged Python files before each commit."
echo ""
echo "To test it, try staging a Python file and committing:"
echo "  git add src/some_file.py"
echo "  git commit -m 'test'"
echo ""
echo "Requirements:"
echo "  - flake8 must be installed: pip install flake8"
echo ""

