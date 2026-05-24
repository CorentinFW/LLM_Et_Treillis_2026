#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

struct BitSet {
    std::vector<std::uint64_t> words;
    std::size_t nbits = 0;

    BitSet() = default;

    explicit BitSet(std::size_t n, bool fill = false)
        : words((n + 63U) / 64U, fill ? ~std::uint64_t{0} : std::uint64_t{0}), nbits(n) {
        if (fill && nbits % 64U != 0U) {
            const std::uint64_t mask = (std::uint64_t{1} << (nbits % 64U)) - 1U;
            words.back() &= mask;
        }
    }

    bool test(std::size_t i) const {
        return (words[i / 64U] >> (i % 64U)) & 1U;
    }

    void set(std::size_t i) {
        words[i / 64U] |= (std::uint64_t{1} << (i % 64U));
    }

    void reset(std::size_t i) {
        words[i / 64U] &= ~(std::uint64_t{1} << (i % 64U));
    }

    std::size_t count() const {
        std::size_t c = 0;
        for (const std::uint64_t w : words) {
            c += static_cast<std::size_t>(__builtin_popcountll(w));
        }
        return c;
    }
};

bool operator==(const BitSet& a, const BitSet& b) {
    return a.nbits == b.nbits && a.words == b.words;
}

bool is_subset_of(const BitSet& a, const BitSet& b) {
    for (std::size_t i = 0; i < a.words.size(); ++i) {
        if ((a.words[i] & ~b.words[i]) != 0U) {
            return false;
        }
    }
    return true;
}

BitSet intersection_of(const BitSet& a, const BitSet& b) {
    BitSet out(a.nbits, false);
    for (std::size_t i = 0; i < a.words.size(); ++i) {
        out.words[i] = a.words[i] & b.words[i];
    }
    return out;
}

BitSet set_difference_of(const BitSet& a, const BitSet& b) {
    BitSet out(a.nbits, false);
    for (std::size_t i = 0; i < a.words.size(); ++i) {
        out.words[i] = a.words[i] & ~b.words[i];
    }
    return out;
}

std::vector<std::string> split_semicolon_line(const std::string& line) {
    std::vector<std::string> tokens;
    std::string current;
    std::stringstream ss(line);
    while (std::getline(ss, current, ';')) {
        if (!current.empty() && current.back() == '\r') {
            current.pop_back();
        }
        tokens.push_back(current);
    }
    if (!line.empty() && line.back() == ';') {
        tokens.push_back("");
    }
    return tokens;
}

std::string trim_copy(const std::string& s) {
    const auto first = s.find_first_not_of(" \t\n\r");
    if (first == std::string::npos) {
        return "";
    }
    const auto last = s.find_last_not_of(" \t\n\r");
    return s.substr(first, last - first + 1U);
}

struct FormalContext {
    std::vector<std::string> objects;
    std::vector<std::string> attributes;
    std::vector<BitSet> object_to_attributes;
    std::vector<BitSet> attribute_to_objects;
};

FormalContext parse_csv_context(const std::string& csv_path) {
    std::ifstream in(csv_path);
    if (!in) {
        throw std::runtime_error("Impossible d'ouvrir le fichier CSV: " + csv_path);
    }

    std::string line;
    if (!std::getline(in, line)) {
        throw std::runtime_error("CSV vide: " + csv_path);
    }

    std::vector<std::string> header = split_semicolon_line(line);
    if (header.size() < 2U) {
        throw std::runtime_error("En-tete CSV invalide (aucun attribut).");
    }

    const std::string first_cell = trim_copy(header[0]);
    if (!first_cell.empty()) {
        throw std::runtime_error("Premiere cellule de l'en-tete attendue vide.");
    }

    FormalContext ctx;
    ctx.attributes.assign(header.begin() + 1, header.end());
    const std::size_t m = ctx.attributes.size();

    for (std::size_t i = 0; i < m; ++i) {
        if (trim_copy(ctx.attributes[i]).empty()) {
            throw std::runtime_error("Nom d'attribut vide a la colonne " + std::to_string(i + 2));
        }
    }

    std::unordered_map<std::string, std::size_t> seen_objects;
    std::size_t line_no = 1;

    while (std::getline(in, line)) {
        ++line_no;
        if (trim_copy(line).empty()) {
            continue;
        }
        std::vector<std::string> row = split_semicolon_line(line);
        if (row.size() != m + 1U) {
            throw std::runtime_error("Nombre de colonnes incoherent ligne " + std::to_string(line_no) +
                                     " (attendu " + std::to_string(m + 1U) + ", obtenu " +
                                     std::to_string(row.size()) + ").");
        }

        const std::string object_name = trim_copy(row[0]);
        if (object_name.empty()) {
            throw std::runtime_error("Nom d'objet vide ligne " + std::to_string(line_no));
        }
        if (seen_objects.find(object_name) != seen_objects.end()) {
            throw std::runtime_error("Objet duplique: " + object_name);
        }
        seen_objects[object_name] = ctx.objects.size();
        ctx.objects.push_back(object_name);

        BitSet attrs(m, false);
        for (std::size_t j = 0; j < m; ++j) {
            const std::string val = trim_copy(row[j + 1]);
            if (val == "1") {
                attrs.set(j);
            } else if (val == "0") {
                // nothing
            } else {
                throw std::runtime_error("Valeur non binaire ligne " + std::to_string(line_no) +
                                         ", colonne " + std::to_string(j + 2) + ": '" + val + "'");
            }
        }
        ctx.object_to_attributes.push_back(std::move(attrs));
    }

    if (ctx.objects.empty()) {
        throw std::runtime_error("Aucun objet trouve dans le CSV.");
    }

    const std::size_t n = ctx.objects.size();
    ctx.attribute_to_objects.assign(m, BitSet(n, false));
    for (std::size_t o = 0; o < n; ++o) {
        for (std::size_t a = 0; a < m; ++a) {
            if (ctx.object_to_attributes[o].test(a)) {
                ctx.attribute_to_objects[a].set(o);
            }
        }
    }

    return ctx;
}

BitSet extent_of_intent(const FormalContext& ctx, const BitSet& intent) {
    BitSet extent(ctx.objects.size(), true);
    for (std::size_t a = 0; a < ctx.attributes.size(); ++a) {
        if (intent.test(a)) {
            extent = intersection_of(extent, ctx.attribute_to_objects[a]);
        }
    }
    return extent;
}

BitSet intent_of_extent(const FormalContext& ctx, const BitSet& extent) {
    BitSet intent(ctx.attributes.size(), true);
    for (std::size_t o = 0; o < ctx.objects.size(); ++o) {
        if (extent.test(o)) {
            intent = intersection_of(intent, ctx.object_to_attributes[o]);
        }
    }
    return intent;
}

std::pair<BitSet, BitSet> closure_with_extent(const FormalContext& ctx, const BitSet& attrs) {
    BitSet ext = extent_of_intent(ctx, attrs);
    BitSet clo = intent_of_extent(ctx, ext);
    return {std::move(clo), std::move(ext)};
}

struct Concept {
    std::size_t id = 0;
    BitSet intent;
    BitSet extent;
    std::vector<std::size_t> shown_attr_idx;
    std::vector<std::size_t> shown_obj_idx;
};

bool next_closure_step(const FormalContext& ctx, BitSet& current_intent, BitSet& current_extent) {
    const std::size_t m = ctx.attributes.size();

    for (std::size_t i = m; i-- > 0;) {
        if (current_intent.test(i)) {
            continue;
        }

        BitSet candidate_seed = current_intent;
        for (std::size_t j = i + 1U; j < m; ++j) {
            candidate_seed.reset(j);
        }
        candidate_seed.set(i);

        auto [candidate_intent, candidate_extent] = closure_with_extent(ctx, candidate_seed);

        bool lectic_ok = true;
        for (std::size_t j = 0; j < i; ++j) {
            if (candidate_intent.test(j) != current_intent.test(j)) {
                lectic_ok = false;
                break;
            }
        }

        if (lectic_ok) {
            current_intent = std::move(candidate_intent);
            current_extent = std::move(candidate_extent);
            return true;
        }
    }
    return false;
}

std::vector<Concept> enumerate_concepts_next_closure(const FormalContext& ctx) {
    std::vector<Concept> concepts;

    BitSet seed(ctx.attributes.size(), false);
    auto [intent0, extent0] = closure_with_extent(ctx, seed);

    while (true) {
        Concept c;
        c.id = concepts.size();
        c.intent = intent0;
        c.extent = extent0;
        concepts.push_back(std::move(c));

        if (!next_closure_step(ctx, intent0, extent0)) {
            break;
        }
    }

    return concepts;
}

std::vector<std::pair<std::size_t, std::size_t>> build_hasse_edges(const std::vector<Concept>& concepts) {
    const std::size_t c = concepts.size();
    std::vector<std::pair<std::size_t, std::size_t>> edges;

    for (std::size_t i = 0; i < c; ++i) {
        for (std::size_t j = 0; j < c; ++j) {
            if (i == j) {
                continue;
            }
            if (!is_subset_of(concepts[i].extent, concepts[j].extent) || concepts[i].extent == concepts[j].extent) {
                continue;
            }

            bool covered = true;
            for (std::size_t k = 0; k < c; ++k) {
                if (k == i || k == j) {
                    continue;
                }
                const bool i_le_k = is_subset_of(concepts[i].extent, concepts[k].extent) &&
                                    !(concepts[i].extent == concepts[k].extent);
                const bool k_le_j = is_subset_of(concepts[k].extent, concepts[j].extent) &&
                                    !(concepts[k].extent == concepts[j].extent);
                if (i_le_k && k_le_j) {
                    covered = false;
                    break;
                }
            }

            if (covered) {
                edges.emplace_back(i, j);
            }
        }
    }

    std::sort(edges.begin(), edges.end());
    return edges;
}

std::string escape_dot_label(std::string s) {
    std::string out;
    out.reserve(s.size() * 2U);
    for (const char ch : s) {
        switch (ch) {
            case '\\':
                out += "\\\\";
                break;
            case '"':
                out += "\\\"";
                break;
            case '{':
            case '}':
            case '|':
            case '<':
            case '>':
                out.push_back('\\');
                out.push_back(ch);
                break;
            default:
                out.push_back(ch);
                break;
        }
    }
    return out;
}

std::string join_names_with_newline(const std::vector<std::size_t>& idx, const std::vector<std::string>& names) {
    if (idx.empty()) {
        return "";
    }
    std::string out;
    for (const std::size_t i : idx) {
        out += escape_dot_label(names[i]);
        out += "\\n";
    }
    return out;
}

void compute_reduced_labels(const std::vector<std::pair<std::size_t, std::size_t>>& edges, std::vector<Concept>& concepts) {
    const std::size_t c = concepts.size();
    std::vector<std::vector<std::size_t>> parents(c);
    std::vector<std::vector<std::size_t>> children(c);

    for (const auto& e : edges) {
        children[e.second].push_back(e.first);
        parents[e.first].push_back(e.second);
    }

    for (std::size_t i = 0; i < c; ++i) {
        BitSet parent_union_intent(concepts[i].intent.nbits, false);
        for (const std::size_t p : parents[i]) {
            for (std::size_t w = 0; w < parent_union_intent.words.size(); ++w) {
                parent_union_intent.words[w] |= concepts[p].intent.words[w];
            }
        }

        BitSet child_union_extent(concepts[i].extent.nbits, false);
        for (const std::size_t ch : children[i]) {
            for (std::size_t w = 0; w < child_union_extent.words.size(); ++w) {
                child_union_extent.words[w] |= concepts[ch].extent.words[w];
            }
        }

        BitSet shown_attrs = set_difference_of(concepts[i].intent, parent_union_intent);
        BitSet shown_objs = set_difference_of(concepts[i].extent, child_union_extent);

        concepts[i].shown_attr_idx.clear();
        concepts[i].shown_obj_idx.clear();
        for (std::size_t a = 0; a < shown_attrs.nbits; ++a) {
            if (shown_attrs.test(a)) {
                concepts[i].shown_attr_idx.push_back(a);
            }
        }
        for (std::size_t o = 0; o < shown_objs.nbits; ++o) {
            if (shown_objs.test(o)) {
                concepts[i].shown_obj_idx.push_back(o);
            }
        }
    }
}

void export_dot(const std::string& dot_path,
                const FormalContext& ctx,
                const std::vector<Concept>& concepts,
                const std::vector<std::pair<std::size_t, std::size_t>>& edges) {
    std::ofstream out(dot_path);
    if (!out) {
        throw std::runtime_error("Impossible d'ecrire le fichier DOT: " + dot_path);
    }

    std::size_t top_id = 0;
    std::size_t bottom_id = 0;

    for (const Concept& c : concepts) {
        if (c.intent.count() == 0U) {
            top_id = c.id;
        }
        if (c.extent.count() == 0U) {
            bottom_id = c.id;
        }
    }

    out << "digraph G {\n";
    out << "    rankdir=BT;\n";

    for (const Concept& c : concepts) {
        const std::string attrs = join_names_with_newline(c.shown_attr_idx, ctx.attributes);
        const std::string objs = join_names_with_newline(c.shown_obj_idx, ctx.objects);

        out << c.id << " [shape=record,style=filled";
        if (c.id == top_id || c.id == bottom_id) {
            out << ",fillcolor=lightblue";
        }
        out << ",label=\"{" << c.id << " (I: " << c.intent.count() << ", E: " << c.extent.count() << ")|"
            << attrs << "|" << objs << "}\"];\n";
    }

    for (const auto& [from, to] : edges) {
        out << "    " << from << " -> " << to << "\n";
    }

    out << "}\n";
}

long long millis_between(const std::chrono::steady_clock::time_point& a,
                         const std::chrono::steady_clock::time_point& b) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(b - a).count();
}

}  // namespace

int main(int argc, char** argv) {
    using clock = std::chrono::steady_clock;

    const auto t0 = clock::now();

    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <input.csv> <output.dot>\n";
        return 1;
    }

    const std::string input_csv = argv[1];
    const std::string output_dot = argv[2];

    try {
        const auto t_parse_start = clock::now();
        FormalContext ctx = parse_csv_context(input_csv);
        const auto t_parse_end = clock::now();

        const auto t_concepts_start = clock::now();
        std::vector<Concept> concepts = enumerate_concepts_next_closure(ctx);
        const auto t_concepts_end = clock::now();

        const auto t_hasse_start = clock::now();
        std::vector<std::pair<std::size_t, std::size_t>> edges = build_hasse_edges(concepts);
        compute_reduced_labels(edges, concepts);
        const auto t_hasse_end = clock::now();

        const auto t_dot_start = clock::now();
        export_dot(output_dot, ctx, concepts, edges);
        const auto t_dot_end = clock::now();

        const auto t1 = clock::now();

        std::cout << "Objets: " << ctx.objects.size() << "\n";
        std::cout << "Attributs: " << ctx.attributes.size() << "\n";
        std::cout << "Concepts: " << concepts.size() << "\n";
        std::cout << "Aretes (Hasse): " << edges.size() << "\n";
        std::cout << "Temps parsing CSV (ms): " << millis_between(t_parse_start, t_parse_end) << "\n";
        std::cout << "Temps calcul concepts (ms): " << millis_between(t_concepts_start, t_concepts_end) << "\n";
        std::cout << "Temps construction Hasse (ms): " << millis_between(t_hasse_start, t_hasse_end) << "\n";
        std::cout << "Temps export DOT (ms): " << millis_between(t_dot_start, t_dot_end) << "\n";
        std::cout << "Temps total (ms): " << millis_between(t0, t1) << "\n";

    } catch (const std::exception& e) {
        std::cerr << "Erreur: " << e.what() << "\n";
        return 2;
    }

    return 0;
}
