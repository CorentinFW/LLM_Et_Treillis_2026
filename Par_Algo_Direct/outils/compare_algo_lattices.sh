#!/bin/bash

###############################################################################
# compare_algo_lattices.sh
# 
# Compares a lattice from an algorithm directory with the reference lattice
# from the Synthetics directory, converting both to full DOT format first.
#
# Usage:
#   ./compare_algo_lattices.sh <algo_dir> <size>
#
# Arguments:
#   algo_dir  : Path to the algorithm directory (e.g., ClaudeSonnet4.6/c++)
#   size      : Size of the example (e.g., 9*9, 30*30)
#
# Example:
#   ./compare_algo_lattices.sh ClaudeSonnet4.6/c++ 9*9
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <algo_dir> <size>"
    echo ""
    echo "Arguments:"
    echo "  algo_dir  : Path to the algorithm directory (e.g., ClaudeSonnet4.6/c++)"
    echo "  size      : Size of the example (e.g., 9*9, 30*30)"
    echo ""
    echo "Example:"
    echo "  $0 ClaudeSonnet4.6/c++ 9*9"
    exit 1
fi

ALGO_DIR="$1"
SIZE="$2"

# Remove * from size to create file prefix (e.g., 9*9 -> eg9_9)
FILE_PREFIX="eg$(echo "$SIZE" | sed 's/\*/_/g')"

# Full paths to the directories
ALGO_SIZE_DIR="$PROJECT_DIR/$ALGO_DIR/$SIZE"
SYNTHETICS_SIZE_DIR="$PROJECT_DIR/Synthetics/$SIZE"

echo "=========================================="
echo "Lattice Comparison"
echo "=========================================="
echo "Algorithm directory: $ALGO_DIR"
echo "Size: $SIZE"
echo ""

# Check if directories exist
if [[ ! -d "$ALGO_SIZE_DIR" ]]; then
    echo "ERROR: Algorithm directory not found: $ALGO_SIZE_DIR"
    exit 1
fi

if [[ ! -d "$SYNTHETICS_SIZE_DIR" ]]; then
    echo "ERROR: Synthetics directory not found: $SYNTHETICS_SIZE_DIR"
    exit 1
fi

# Find the actual .dot files
ALGO_DOT="$ALGO_SIZE_DIR/$FILE_PREFIX.dot"
SYNTHETICS_DOT="$SYNTHETICS_SIZE_DIR/$FILE_PREFIX.dot"

if [[ ! -f "$ALGO_DOT" ]]; then
    echo "ERROR: Algorithm DOT file not found: $ALGO_DOT"
    exit 1
fi

if [[ ! -f "$SYNTHETICS_DOT" ]]; then
    echo "ERROR: Synthetics DOT file not found: $SYNTHETICS_DOT"
    exit 1
fi

echo "Source 1 (Algorithm): $ALGO_DOT"
echo "Source 2 (Synthetics): $SYNTHETICS_DOT"
echo ""

# Create temporary directory for full DOT files
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

ALGO_FULL_DOT="$TEMP_DIR/algo_full.dot"
SYNTHETICS_FULL_DOT="$TEMP_DIR/synthetics_full.dot"

echo "Converting to full DOT format..."
echo "  - Converting algorithm lattice..."
python3 "$SCRIPT_DIR/induced_to_full_dot.py" "$ALGO_DOT" "$ALGO_FULL_DOT"

echo "  - Converting synthetics lattice..."
python3 "$SCRIPT_DIR/induced_to_full_dot.py" "$SYNTHETICS_DOT" "$SYNTHETICS_FULL_DOT"

echo ""
echo "Comparing lattices..."
echo "=========================================="
echo ""

# Run comparison and capture both output and exit code
python3 "$SCRIPT_DIR/compare_lattices.py" "$ALGO_FULL_DOT" "$SYNTHETICS_FULL_DOT"
COMPARISON_EXIT_CODE=$?

echo ""
echo "=========================================="

if [[ $COMPARISON_EXIT_CODE -eq 0 ]]; then
    echo "✓ Lattices are EQUIVALENT"
else
    echo "✗ Lattices are DIFFERENT"
fi

exit $COMPARISON_EXIT_CODE
