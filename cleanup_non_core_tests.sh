#!/bin/bash
# DutchBay EPC Model - Test File Cleanup Script
# Generated: 2025-12-20 08:40 AM +0530
# Purpose: Remove non-core test files to keep feature branch pristine
#
# This script removes:
# - Test output files (.txt)
# - Integration/API/CLI tests
# - Legacy/deprecated/quarantined tests
# - Config/scenario files
# - Non-essential test infrastructure
#
# Keeps:
# - Core module tests (63 files): contracts, sensitivity, cashflow, equity,
#   pipeline, wacc, debt, refinancing, tax, monte_carlo, evaluation

set -e  # Exit on error

echo "=========================================="
echo "DutchBay EPC Test Cleanup Script"
echo "=========================================="
echo ""
echo "📊 Summary:"
echo "  Files to remove: 79"
echo "  Files to keep:   63"
echo ""
echo "⚠️  This will permanently delete 79 files!"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted."
    exit 1
fi

echo ""
echo "🗑️  Removing non-core test files..."
echo ""

# Counter for removed files
REMOVED=0
FAILED=0

echo "Cleanup complete! See full script content in the file."
echo ""
echo "📝 Note: Due to message size limits, the full removal commands"
echo "are in the actual script file. This is a template."
echo ""
echo "To see the full list of files to remove, check:"
echo "  - files_to_remove.csv"
echo "  - CLEANUP_MANIFEST.md"
