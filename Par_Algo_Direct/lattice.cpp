/*
 * ============================================================
 *  lattice.cpp  --  Formal Concept Lattice builder
 * ============================================================
 *
 * COMPILATION
 *   g++ -std=c++17 -O2 -o lattice lattice.cpp
 *
 * USAGE
 *   ./lattice input.csv
 *
 * OUTPUT
 *   lattice.dot   (Graphviz source, always written)
 *   lattice.pdf   (rendered diagram, requires Graphviz / dot)
 *
 * DEPENDENCIES
 *   None beyond the C++17 standard library.
 *   Graphviz (dot) must be installed to produce the PDF:
 *       sudo apt install graphviz     (Debian/Ubuntu)
 *       brew install graphviz         (macOS)
 *
 * ──────────────────────────────────────────────────────────
 * CSV FORMAT
 *
 *   Delimiter : comma (',') or semicolon (';') -- auto-detected.
 *   Header row: optional first row whose first cell is empty or
 *               non-numeric (attribute names are read from it).
 *   Name col  : optional first column with object / attribute names
 *               (auto-detected if first data cell is non-numeric).
 *   Data cells: '1' (or any non-zero token) = object has attribute.
 *               '0' (or empty)              = object lacks attribute.
 *   Comment lines starting with '#' are ignored.
 *
 *   Example A -- minimal, no names, comma-delimited:
 *       1,0,1,0
 *       0,1,1,1
 *       1,1,0,0
 *       0,0,1,1
 *
 *   Example B -- with names, semicolon-delimited:
 *       ;flies;nocturnal;feathered
 *       eagle;1;0;1
 *       bat;1;1;0
 *       penguin;0;0;1
 *
 * ──────────────────────────────────────────────────────────
 * ALGORITHM
 *
 *   Phase 1 -- CbO enumeration  (Kuznetsov & Obiedkov, 2002)
 *     Close-by-One: a DFS algorithm that constructs the concept
 *     lattice in a SINGLE RECURSIVE TRAVERSAL.  Each formal
 *     concept is visited and generated exactly once; no global
 *     re-scan is ever performed.
 *
 *     Starting from the supremum concept (all objects, shared
 *     attributes), each branch of the DFS extends the current
 *     closed set by one new attribute and recurses only when a
 *     canonicity condition is satisfied.  This guarantees that
 *     every concept appears exactly once in the DFS tree.
 *
 *   Phase 2 -- Hasse diagram (transitive reduction)
 *     A single O(N^2 * M) pass over N collected concepts removes
 *     every non-cover inclusion edge, yielding the covering
 *     relation (immediate parents / children in the lattice).
 *
 * ============================================================
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cctype>

/* ============================================================
 *  Global context
 * ============================================================ */

static int G = 0;   // number of objects
static int M = 0;   // number of attributes

// ctx[g][m] == true  iff object g has attribute m.
static std::vector<std::vector<bool>> ctx;

/* ============================================================
 *  Concept node
 * ============================================================ */
struct Concept {
    std::vector<int> extent;    // sorted object indices
    std::vector<int> intent;    // sorted attribute indices (closed set)
    std::vector<int> children;  // Hasse: direct sub-concepts   (larger intent)
    std::vector<int> parents;   // Hasse: direct super-concepts (smaller intent)
};

static std::vector<Concept> lattice;

/* ============================================================
 *  Helper: is sorted vector A a subset of sorted vector B?
 * ============================================================ */
static bool isSubset(const std::vector<int>& A,
                     const std::vector<int>& B) {
    size_t i = 0, j = 0;
    while (i < A.size() && j < B.size()) {
        if      (A[i] == B[j]) { ++i; ++j; }
        else if (A[i] >  B[j]) { ++j; }
        else    return false;
    }
    return i == A.size();
}

/* ============================================================
 *  Compute extent of a (boolean) intent vector:
 *    extent(B) = { g : for all m in B, ctx[g][m] }
 * ============================================================ */
static std::vector<int> extentOf(const std::vector<bool>& intent) {
    std::vector<int> ext;
    ext.reserve(G);
    for (int g = 0; g < G; ++g) {
        bool ok = true;
        for (int m = 0; m < M; ++m)
            if (intent[m] && !ctx[g][m]) { ok = false; break; }
        if (ok) ext.push_back(g);
    }
    return ext;
}

/* ============================================================
 *  Compute the closure (double-prime) of a boolean attribute set:
 *    close(B) = (extentOf(B))' = { m : for all g in ext(B), ctx[g][m] }
 *  If the extent is empty, the closure is the full attribute set.
 * ============================================================ */
static std::vector<bool> closureOf(const std::vector<bool>& intent) {
    std::vector<int> ext = extentOf(intent);
    std::vector<bool> closed(M, true);
    if (ext.empty()) return closed;   // infimum: all attributes
    for (int g : ext)
        for (int m = 0; m < M; ++m)
            if (!ctx[g][m]) closed[m] = false;
    return closed;
}

/* ============================================================
 *  CbO -- Close-by-One  (single-pass DFS concept enumeration)
 *
 *  Parameters:
 *    curExtent  -- extent of the current concept (sorted)
 *    curIntent  -- intent of the current concept  (boolean vector)
 *    startAttr  -- first attribute index to try in this branch
 *
 *  The canonicity condition ensures that each concept is
 *  reachable by exactly one DFS path:
 *    close(curIntent u {j}) must not introduce any attribute
 *    k < j that was absent from curIntent.
 * ============================================================ */
static void CbO(const std::vector<int>&  curExtent,
                const std::vector<bool>& curIntent,
                int startAttr) {

    // Record current concept.
    Concept c;
    c.extent = curExtent;
    for (int m = 0; m < M; ++m)
        if (curIntent[m]) c.intent.push_back(m);
    lattice.push_back(std::move(c));

    // Try extending with each new attribute j >= startAttr.
    for (int j = startAttr; j < M; ++j) {
        if (curIntent[j]) continue;

        // Compute closure of curIntent u {j}.
        std::vector<bool> trial = curIntent;
        trial[j] = true;
        std::vector<bool> closed = closureOf(trial);

        // Canonicity check: no attribute k < j introduced that
        // was not already in curIntent.
        bool canonical = true;
        for (int k = 0; k < j; ++k)
            if (closed[k] && !curIntent[k]) { canonical = false; break; }
        if (!canonical) continue;

        // Recurse on child concept.
        CbO(extentOf(closed), closed, j + 1);
    }
}

/* ============================================================
 *  Build the lattice:
 *    1. Compute supremum (all objects, shared attributes).
 *    2. Run CbO for single-pass enumeration.
 *    3. Compute Hasse diagram via transitive reduction.
 * ============================================================ */
static void buildLattice() {

    // Supremum = (G, G') : all objects, attributes shared by all objects.
    std::vector<bool> topIntent(M, true);
    for (int g = 0; g < G; ++g)
        for (int m = 0; m < M; ++m)
            if (!ctx[g][m]) topIntent[m] = false;

    std::vector<int> topExtent;
    for (int g = 0; g < G; ++g) topExtent.push_back(g);

    // Single-pass CbO enumeration.
    CbO(topExtent, topIntent, 0);

    int N = (int)lattice.size();

    // Hasse diagram: transitive reduction.
    // inc[i][j] = true  iff  intent[i]  is a strict subset of  intent[j].
    std::vector<std::vector<bool>> inc(N, std::vector<bool>(N, false));
    for (int i = 0; i < N; ++i)
        for (int j = 0; j < N; ++j)
            if (i != j &&
                lattice[i].intent != lattice[j].intent &&
                isSubset(lattice[i].intent, lattice[j].intent))
                inc[i][j] = true;

    // Remove non-cover edges: if i->k and k->j, then i->j is not a cover.
    for (int k = 0; k < N; ++k)
        for (int i = 0; i < N; ++i) if (inc[i][k])
            for (int j = 0; j < N; ++j) if (inc[k][j])
                inc[i][j] = false;

    for (int i = 0; i < N; ++i)
        for (int j = 0; j < N; ++j)
            if (inc[i][j]) {
                lattice[i].children.push_back(j);
                lattice[j].parents.push_back(i);
            }
}

/* ============================================================
 *  CSV parser
 *
 *  Auto-detects:
 *    - delimiter  (',' or ';')
 *    - header row (first row whose first cell is empty or non-numeric)
 *    - object name column (first data column with non-numeric values)
 *
 *  Fills ctx, G, M and optionally objNames / attrNames.
 * ============================================================ */
static std::string trim(const std::string& s) {
    auto b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    auto e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

static bool isNumericCell(const std::string& s) {
    // Returns true if s looks like a data cell (empty, "0", "1", digits...).
    if (s.empty()) return true;
    for (char c : s) if (!std::isdigit((unsigned char)c) && c != '.' && c != '-') return false;
    return true;
}

static char detectDelimiter(const std::string& line) {
    size_t sc = std::count(line.begin(), line.end(), ';');
    size_t cc = std::count(line.begin(), line.end(), ',');
    return (sc >= cc) ? ';' : ',';
}

static std::vector<std::string> splitLine(const std::string& line, char delim) {
    std::vector<std::string> tokens;
    std::istringstream ss(line);
    std::string t;
    while (std::getline(ss, t, delim))
        tokens.push_back(trim(t));
    return tokens;
}

static void parseCSV(const std::string& filename,
                     std::vector<std::string>& objNames,
                     std::vector<std::string>& attrNames) {
    std::ifstream fin(filename);
    if (!fin.is_open()) {
        std::cerr << "Error: cannot open '" << filename << "'\n";
        std::exit(1);
    }

    // Collect all non-comment lines.
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(fin, line)) {
        std::string t = trim(line);
        if (!t.empty() && t[0] != '#') lines.push_back(t);
    }
    if (lines.empty()) { std::cerr << "Error: empty file.\n"; std::exit(1); }

    // Detect delimiter from first line.
    char delim = detectDelimiter(lines[0]);

    // Detect if there is a header row and/or a name column.
    auto firstRow = splitLine(lines[0], delim);

    // A header row is present when the first cell is either:
    //   - empty            (e.g.  ";attr1;attr2"  -- name column also present)
    //   - non-numeric text (e.g.  "attr1,attr2,…" -- attributes only, no name col)
    bool firstCellEmpty    = !firstRow.empty() && firstRow[0].empty();
    bool firstCellTextual  = !firstRow.empty() && !firstRow[0].empty()
                             && !isNumericCell(firstRow[0]);
    bool hasHeader  = firstCellEmpty || firstCellTextual;
    bool hasNameCol = firstCellEmpty;   // empty first header cell = name column

    int dataStart = hasHeader ? 1 : 0;
    // Also detect name column from first data row (non-numeric first cell).
    if (dataStart < (int)lines.size()) {
        auto firstDataRow = splitLine(lines[dataStart], delim);
        if (!firstDataRow.empty() && !isNumericCell(firstDataRow[0]))
            hasNameCol = true;
    }

    // Read attribute names from header row (if present).
    if (hasHeader) {
        int start = hasNameCol ? 1 : 0;
        for (int i = start; i < (int)firstRow.size(); ++i)
            attrNames.push_back(firstRow[i].empty()
                                ? ("A" + std::to_string(attrNames.size()+1))
                                : firstRow[i]);
    }

    // Read data rows.
    for (int r = dataStart; r < (int)lines.size(); ++r) {
        auto row = splitLine(lines[r], delim);
        if (row.empty()) continue;

        int colStart = hasNameCol ? 1 : 0;
        if (hasNameCol && !row.empty())
            objNames.push_back(row[0].empty()
                               ? ("G" + std::to_string(objNames.size()+1))
                               : row[0]);
        else
            objNames.push_back("G" + std::to_string(objNames.size()+1));

        std::vector<bool> rowAttrs;
        for (int c = colStart; c < (int)row.size(); ++c)
            rowAttrs.push_back(row[c] != "0" && !row[c].empty());

        ctx.push_back(rowAttrs);
    }

    if (ctx.empty()) { std::cerr << "Error: no data rows.\n"; std::exit(1); }

    G = (int)ctx.size();
    // M = number of columns (consistent across rows).
    int cols = (int)ctx[0].size();
    for (auto& row : ctx) {
        if ((int)row.size() != cols) {
            // Pad or truncate to majority width.
            row.resize(cols, false);
        }
    }
    M = cols;

    // Fill default attribute names if not read from header.
    while ((int)attrNames.size() < M)
        attrNames.push_back("A" + std::to_string(attrNames.size()+1));
    attrNames.resize(M);   // truncate if header had extra cols
}

/* ============================================================
 *  DOT export
 * ============================================================ */
static std::string dotEscape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c=='<'||c=='>'||c=='"'||c=='{'||c=='}'||c=='|'||c=='\\')
            out += '\\';
        out += c;
    }
    return out;
}

static void writeDOT(const std::string& dotFile,
                     const std::vector<std::string>& objNames,
                     const std::vector<std::string>& attrNames) {
    std::ofstream fout(dotFile);
    if (!fout.is_open()) {
        std::cerr << "Error: cannot write '" << dotFile << "'\n";
        std::exit(1);
    }

    fout << "digraph ConceptLattice {\n"
         << "  rankdir=TB;\n"
         << "  node [shape=record, fontname=\"Helvetica\", fontsize=11,"
            " style=filled, fillcolor=lightyellow];\n"
         << "  edge [dir=none, color=gray40];\n\n";

    for (int i = 0; i < (int)lattice.size(); ++i) {
        const Concept& c = lattice[i];
        std::string extStr, intStr;
        for (int g : c.extent) {
            if (!extStr.empty()) extStr += ", ";
            extStr += objNames[g];
        }
        for (int m : c.intent) {
            if (!intStr.empty()) intStr += ", ";
            intStr += attrNames[m];
        }
        if (extStr.empty()) extStr = "{}";
        if (intStr.empty()) intStr = "{}";

        fout << "  n" << i
             << " [label=\"{"
             << dotEscape(extStr) << "|"
             << dotEscape(intStr) << "}\"];\n";
    }
    fout << "\n";

    for (int i = 0; i < (int)lattice.size(); ++i)
        for (int j : lattice[i].children)
            fout << "  n" << i << " -> n" << j << ";\n";

    fout << "}\n";
    std::cout << "DOT written : " << dotFile << "\n";
}

/* ============================================================
 *  main
 * ============================================================ */
int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " input.csv\n";
        return 1;
    }

    const std::string csvFile = argv[1];
    const std::string dotFile = "lattice.dot";
    const std::string pdfFile = "lattice.pdf";

    // 1. Read context.
    std::vector<std::string> objNames, attrNames;
    parseCSV(csvFile, objNames, attrNames);
    std::cout << "Context   : " << G << " object(s), "
              << M << " attribute(s)\n";

    // 2. Build concept lattice (single-pass CbO).
    buildLattice();
    std::cout << "Concepts  : " << lattice.size() << "\n";

    // 3. Print concepts.
    for (int i = 0; i < (int)lattice.size(); ++i) {
        const Concept& c = lattice[i];
        std::cout << "  [" << i << "]  extent={";
        for (size_t k = 0; k < c.extent.size(); ++k) {
            if (k) std::cout << ',';
            std::cout << objNames[c.extent[k]];
        }
        std::cout << "}  intent={";
        for (size_t k = 0; k < c.intent.size(); ++k) {
            if (k) std::cout << ',';
            std::cout << attrNames[c.intent[k]];
        }
        std::cout << "}  children=[";
        for (size_t k = 0; k < c.children.size(); ++k) {
            if (k) std::cout << ',';
            std::cout << c.children[k];
        }
        std::cout << "]\n";
    }

    // 4. Write DOT.
    writeDOT(dotFile, objNames, attrNames);

    // 5. Render to PDF.
    std::string cmd = "dot -Tpdf " + dotFile + " -o " + pdfFile;
    std::cout << "Running   : " << cmd << "\n";
    int ret = std::system(cmd.c_str());
    if (ret != 0) {
        std::cerr << "Warning   : Graphviz 'dot' failed or is not installed.\n"
                  << "            The file '" << dotFile
                  << "' is ready for manual rendering.\n";
        return 1;
    }
    std::cout << "PDF written: " << pdfFile << "\n";
    return 0;
}
