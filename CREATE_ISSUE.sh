#!/bin/bash
# Script to create the GitHub issue for Enhanced Word Sidebar feature
# 
# This script attempts to create the issue using GitHub CLI.
# If authentication fails, it provides instructions for manual creation.

set -e

REPO="kvchitrapu/ambuda"
TITLE="Enhanced Word Sidebar for Sanskrit Learning"
BODY_FILE="FEATURE_ISSUE.md"
LABELS="enhancement"

echo "════════════════════════════════════════════════════════════════"
echo "  GitHub Issue Creation: Enhanced Word Sidebar"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo ""
    echo "Please create the issue manually:"
    echo "1. Go to: https://github.com/$REPO/issues/new"
    echo "2. Title: $TITLE"
    echo "3. Copy content from: $BODY_FILE"
    echo "4. Add labels: $LABELS"
    echo ""
    exit 1
fi

# Check if body file exists
if [ ! -f "$BODY_FILE" ]; then
    echo "❌ Issue body file not found: $BODY_FILE"
    exit 1
fi

echo "📋 Attempting to create GitHub issue..."
echo "   Repository: $REPO"
echo "   Title: $TITLE"
echo "   Labels: $LABELS"
echo ""

# Try to create the issue
if gh issue create \
    --repo "$REPO" \
    --title "$TITLE" \
    --body-file "$BODY_FILE" \
    --label "$LABELS" 2>&1; then
    echo ""
    echo "✅ Issue created successfully!"
    echo ""
else
    EXIT_CODE=$?
    echo ""
    echo "❌ Failed to create issue automatically (exit code: $EXIT_CODE)"
    echo ""
    echo "This usually means you need to authenticate or don't have permissions."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  MANUAL CREATION INSTRUCTIONS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "1. Authenticate GitHub CLI:"
    echo "   gh auth login"
    echo ""
    echo "   OR"
    echo ""
    echo "2. Create issue manually:"
    echo "   → Go to: https://github.com/$REPO/issues/new"
    echo "   → Title: $TITLE"
    echo "   → Copy entire content from: $BODY_FILE"
    echo "   → Add labels: enhancement, pedagogy, reader, learner-experience"
    echo "   → Submit"
    echo ""
    echo "3. Verify issue content:"
    echo "   → Problem statement clearly describes user needs"
    echo "   → User stories for different skill levels"
    echo "   → Proposed solution at high level (not implementation)"
    echo "   → Success criteria and benefits listed"
    echo ""
    exit 1
fi

echo "════════════════════════════════════════════════════════════════"
echo "  Issue Creation Complete!"
echo "════════════════════════════════════════════════════════════════"
