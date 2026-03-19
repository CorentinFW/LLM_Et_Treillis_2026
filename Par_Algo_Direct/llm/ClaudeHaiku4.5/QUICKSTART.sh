#!/bin/bash
# Quick Start Guide for Lattice Generator

echo "FORMAL CONCEPT ANALYSIS LATTICE GENERATOR - Quick Start"
echo "======================================================"
echo ""

# Change to project directory
cd "$(dirname "$0")"

echo "1. Compilation:"
echo "   g++ -std=c++17 -O2 -o lattice_generator lattice_generator.cpp"
echo ""

echo "2. Usage:"
echo "   ./lattice_generator <input.csv>"
echo "   Output: <input.dot>"
echo ""

echo "3. Example with Animals11.csv:"
echo "   ./lattice_generator Format/Animals11.csv"
echo "   Result: Generated Format/Animals11.dot with 13 formal concepts"
echo ""

echo "4. Visualization (requires Graphviz):"
echo "   dot -Tpng Format/Animals11.dot -o lattice.png"
echo "   dot -Tsvg Format/Animals11.dot -o lattice.svg"
echo ""

echo "5. Input CSV Format:"
echo "   Line 1:  ;attr1;attr2;attr3;...;attrN"
echo "   Line 2+: object_name;0/1;0/1;...;0/1"
echo ""

echo "6. Output DOT Structure:"
echo "   - Each node = one formal concept"
echo "   - Node ID (I: intent_size, E: extent_size)"
echo "   - Edges = covering relations (intent-ordered)"
echo "   - rankdir=BT for bottom-to-top layout"
echo ""

echo "For detailed information, see: README.md"
