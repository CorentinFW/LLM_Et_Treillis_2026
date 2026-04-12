/**
 * lattice.cpp
 *
 * Formal Concept Analysis (FCA) – Concept Lattice Builder
 *
 * Reads a binary object×attribute CSV context, enumerates all formal concepts
 * using Ganter's Next Closure algorithm (1984), computes the Hasse diagram
 * (direct cover relations only, no transitive edges), and exports the result
 * as a Graphviz DOT file.
 *
 * Compile:  g++ -std=c++17 -O2 -o lattice lattice.cpp
 * Usage:    ./lattice <input.csv>
 *
 * CSV format expected:
 *   First line : empty field; attr1; attr2; ...
 *   Other lines: objectName; 0/1; 0/1; ...
 *
 * Output: <input_basename>.dot
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>
#include <numeric>
#include <chrono>

// ============================================================
// Data structures
// ============================================================

struct FormalContext {
    std::vector<std::string> objects;      // G
    std::vector<std::string> attributes;   // M
    std::vector<std::vector<bool>> table;  // table[g][m] = I(g,m)

    int nObj()  const { return static_cast<int>(objects.size()); }
    int nAttr() const { return static_cast<int>(attributes.size()); }
};

struct Concept {
    std::vector<bool> extent;  // subset of G
    std::vector<bool> intent;  // subset of M (closed set)
};

// ============================================================
// CSV parsing
// ============================================================

FormalContext parseCSV(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: cannot open file '" << filename << "'\n";
        std::exit(1);
    }

    FormalContext ctx;
    std::string line;
    bool firstLine = true;

    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;

        std::vector<std::string> tokens;
        std::stringstream ss(line);
        std::string tok;
        while (std::getline(ss, tok, ';')) tokens.push_back(tok);

        if (firstLine) {
            for (std::size_t i = 1; i < tokens.size(); ++i)
                ctx.attributes.push_back(tokens[i]);
            firstLine = false;
        } else {
            if (static_cast<int>(tokens.size()) < 1 + ctx.nAttr()) {
                std::cerr << "Error: malformed CSV row: " << line << "\n";
                std::exit(1);
            }
            ctx.objects.push_back(tokens[0]);
            std::vector<bool> row;
            row.reserve(ctx.nAttr());
            for (int m = 0; m < ctx.nAttr(); ++m)
                row.push_back(tokens[1 + m] == "1");
            ctx.table.push_back(std::move(row));
        }
    }

    if (ctx.nObj() == 0 || ctx.nAttr() == 0) {
        std::cerr << "Error: empty context read from '" << filename << "'\n";
        std::exit(1);
    }
    return ctx;
}

// ============================================================
// Derivation operators
// ============================================================

// A^top : given objects A, compute common attributes
static std::vector<bool> primeObjects(const FormalContext& ctx,
                                      const std::vector<bool>& A) {
    int nM = ctx.nAttr();
    std::vector<bool> result(nM, true);
    bool anyObj = false;
    for (int g = 0; g < ctx.nObj(); ++g) {
        if (A[g]) {
            anyObj = true;
            for (int m = 0; m < nM; ++m)
                if (!ctx.table[g][m]) result[m] = false;
        }
    }
    if (!anyObj) std::fill(result.begin(), result.end(), true);
    return result;
}

// B^bot : given attributes B, compute objects owning all of them
static std::vector<bool> primeAttrs(const FormalContext& ctx,
                                    const std::vector<bool>& B) {
    int nG = ctx.nObj();
    std::vector<bool> result(nG, true);
    bool anyAttr = false;
    for (int m = 0; m < ctx.nAttr(); ++m) {
        if (B[m]) {
            anyAttr = true;
            for (int g = 0; g < nG; ++g)
                if (!ctx.table[g][m]) result[g] = false;
        }
    }
    if (!anyAttr) std::fill(result.begin(), result.end(), true);
    return result;
}

// Attribute closure h(B) = (B^bot)^top = B''
static std::vector<bool> attrClosure(const FormalContext& ctx,
                                     const std::vector<bool>& B) {
    return primeObjects(ctx, primeAttrs(ctx, B));
}

// ============================================================
// Next Closure algorithm (Ganter, 1984)
// ============================================================

static bool nextClosure(const FormalContext& ctx, std::vector<bool>& B) {
    int n = ctx.nAttr();
    for (int i = n - 1; i >= 0; --i) {
        if (B[i]) {
            B[i] = false;
            continue;
        }
        std::vector<bool> seed(n, false);
        for (int j = 0; j < i; ++j) seed[j] = B[j];
        seed[i] = true;

        std::vector<bool> Y = attrClosure(ctx, seed);

        bool lectOK = true;
        for (int j = 0; j < i; ++j) {
            if (Y[j] && !B[j]) { lectOK = false; break; }
        }
        if (lectOK) {
            B = std::move(Y);
            return true;
        }
    }
    return false;
}

// ============================================================
// Concept enumeration
// ============================================================

static std::vector<Concept> enumerateConcepts(const FormalContext& ctx) {
    std::vector<Concept> concepts;

    std::vector<bool> intent(ctx.nAttr(), false);
    intent = attrClosure(ctx, intent);

    do {
        Concept c;
        c.intent = intent;
        c.extent = primeAttrs(ctx, intent);
        concepts.push_back(std::move(c));
    } while (nextClosure(ctx, intent));

    return concepts;
}

// ============================================================
// Sorting concepts
// ============================================================

static int popcount(const std::vector<bool>& v) {
    int c = 0;
    for (bool b : v) if (b) ++c;
    return c;
}

static bool conceptOrder(const Concept& a, const Concept& b,
                          const std::vector<std::string>& attrNames) {
    int sA = popcount(a.intent), sB = popcount(b.intent);
    if (sA != sB) return sA < sB;

    std::vector<std::string> namesA, namesB;
    for (int m = 0; m < (int)attrNames.size(); ++m) {
        if (a.intent[m]) namesA.push_back(attrNames[m]);
        if (b.intent[m]) namesB.push_back(attrNames[m]);
    }
    std::sort(namesA.begin(), namesA.end());
    std::sort(namesB.begin(), namesB.end());
    return namesA < namesB;
}

// ============================================================
// Hasse diagram
// ============================================================

static bool isSubset(const std::vector<bool>& A, const std::vector<bool>& B) {
    for (std::size_t i = 0; i < A.size(); ++i)
        if (A[i] && !B[i]) return false;
    return true;
}

// Returns pairs (i, j): concept i (larger intent = more specific) directly
// covers concept j (smaller intent = more general).
// Edge i -> j in the DOT file; with rankdir=BT renders j visually higher.
static std::vector<std::pair<int,int>> computeHasse(const std::vector<Concept>& concepts) {
    int n = static_cast<int>(concepts.size());

    // above[i][j] = true when concept[i].intent strictly contains concept[j].intent
    std::vector<std::vector<bool>> above(n, std::vector<bool>(n, false));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j)
            if (i != j &&
                isSubset(concepts[j].intent, concepts[i].intent) &&
                concepts[j].intent != concepts[i].intent)
                above[i][j] = true;

    std::vector<std::pair<int,int>> covers;
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            if (!above[i][j]) continue;
            bool direct = true;
            for (int k = 0; k < n && direct; ++k)
                if (k != i && k != j && above[i][k] && above[k][j])
                    direct = false;
            if (direct) covers.emplace_back(i, j);
        }
    }
    return covers;
}

// ============================================================
// DOT export helpers
// ============================================================

static std::string escapeLabel(const std::string& s) {
    std::string result;
    result.reserve(s.size() + 4);
    for (char c : s) {
        if (c == '{' || c == '}' || c == '<' || c == '>' ||
            c == '|' || c == '\\' || c == '"')
            result += '\\';
        result += c;
    }
    return result;
}

// ============================================================
// DOT export
// ============================================================

static void exportDOT(const FormalContext& ctx,
                      std::vector<Concept>& concepts,
                      const std::string& outfile) {
    // 1. Sort
    std::sort(concepts.begin(), concepts.end(),
              [&](const Concept& a, const Concept& b) {
                  return conceptOrder(a, b, ctx.attributes);
              });

    int n = static_cast<int>(concepts.size());

    // 2. Hasse diagram
    auto covers = computeHasse(concepts);

    // 3. New attributes: h({m}) == concept k's intent
    std::vector<int> attrConcept(ctx.nAttr(), -1);
    for (int m = 0; m < ctx.nAttr(); ++m) {
        std::vector<bool> singleton(ctx.nAttr(), false);
        singleton[m] = true;
        std::vector<bool> closed = attrClosure(ctx, singleton);
        for (int k = 0; k < n; ++k) {
            if (concepts[k].intent == closed) { attrConcept[m] = k; break; }
        }
    }

    // 4. New objects: h(row_g) == concept k's intent
    std::vector<int> objConcept(ctx.nObj(), -1);
    for (int g = 0; g < ctx.nObj(); ++g) {
        std::vector<bool> closed = attrClosure(ctx, ctx.table[g]);
        for (int k = 0; k < n; ++k) {
            if (concepts[k].intent == closed) { objConcept[g] = k; break; }
        }
    }

    // 5. Build per-concept lists
    std::vector<std::vector<int>> newAttrs(n), newObjs(n);
    for (int m = 0; m < ctx.nAttr(); ++m)
        if (attrConcept[m] >= 0) newAttrs[attrConcept[m]].push_back(m);
    for (int g = 0; g < ctx.nObj(); ++g)
        if (objConcept[g] >= 0)  newObjs[objConcept[g]].push_back(g);

    // 6. Write DOT
    std::ofstream out(outfile);
    if (!out.is_open()) {
        std::cerr << "Error: cannot write to file '" << outfile << "'\n";
        std::exit(1);
    }

    out << "digraph G {\n";
    out << "    rankdir=BT;\n";

    for (int k = 0; k < n; ++k) {
        int nbIntent  = popcount(concepts[k].intent);
        int nbExtent  = popcount(concepts[k].extent);
        int nbNewObjs = static_cast<int>(newObjs[k].size());

        // Color
        std::string colorPart;
        if      (nbNewObjs == 0)  colorPart = "fillcolor=lightblue,";
        else if (nbNewObjs >= 2)  colorPart = "fillcolor=orange,";
        else                      colorPart = "";   // exactly 1 new object

        // New-attribute field  (with trailing \n if non-empty)
        std::string attrsField;
        for (int idx : newAttrs[k]) {
            if (!attrsField.empty()) attrsField += "\\n";
            attrsField += escapeLabel(ctx.attributes[idx]);
        }
        if (!attrsField.empty()) attrsField += "\\n";

        // New-object field  (with trailing \n if non-empty)
        std::string objsField;
        for (int idx : newObjs[k]) {
            if (!objsField.empty()) objsField += "\\n";
            objsField += escapeLabel(ctx.objects[idx]);
        }
        if (!objsField.empty()) objsField += "\\n";

        out << k
            << " [shape=record,style=filled," << colorPart
            << "label=\"{" << k
            << " (I: " << nbIntent << ", E: " << nbExtent << ")"
            << "|" << attrsField
            << "|" << objsField
            << "}\"];\n";
    }

    for (auto& [from, to] : covers)
        out << "    " << from << " -> " << to << "\n";

    out << "}\n";
}

// ============================================================
// Main
// ============================================================

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <input.csv>\n";
        return 1;
    }

    const auto startTime = std::chrono::steady_clock::now();

    const std::string inputFile = argv[1];

    // Derive output filename: replace extension with .dot
    std::size_t dot = inputFile.rfind('.');
    std::string outputFile = (dot != std::string::npos
                              ? inputFile.substr(0, dot)
                              : inputFile) + ".dot";

    // Step 1 – Parse CSV
    FormalContext ctx = parseCSV(inputFile);
    std::cerr << "Context loaded: " << ctx.nObj() << " objects, "
              << ctx.nAttr() << " attributes.\n";

    // Step 2 – Enumerate all formal concepts (Next Closure)
    std::vector<Concept> concepts = enumerateConcepts(ctx);
    std::cerr << "Formal concepts found: " << concepts.size() << "\n";

    // Step 3 – Sort, Hasse, new attrs/objs, write DOT
    exportDOT(ctx, concepts, outputFile);
    std::cerr << "DOT file written to: " << outputFile << "\n";

    const auto endTime = std::chrono::steady_clock::now();
    const auto elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime).count();
    std::cerr << "Execution time: " << elapsedMs << " ms\n";

    return 0;
}
