#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <map>
#include <algorithm>
#include <chrono>
#include <iomanip>

struct Concept {
    int id;
    std::string intent;
    std::vector<std::string> extent;
};

inline bool isSubset(const std::string& a, const std::string& b) {
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] == '1' && b[i] == '0') return false;
    }
    return true;
}

std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <input.csv> <output.dot>\n";
        return 1;
    }

    std::ifstream csv_stream(argv[1]);
    if (!csv_stream.is_open()) {
        std::cerr << "Error: Cannot open input file " << argv[1] << "\n";
        return 1;
    }

    std::ofstream dot_stream(argv[2]);
    if (!dot_stream.is_open()) {
        std::cerr << "Error: Cannot open output file " << argv[2] << "\n";
        return 1;
    }

    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    if (!std::getline(csv_stream, line)) {
        std::cerr << "Error: Empty input file\n";
        return 1;
    }

    std::vector<std::string> attr_names;
    std::stringstream header_ss(trim(line));
    std::string attr;
    while (std::getline(header_ss, attr, ';')) {
        attr_names.push_back(trim(attr));
    }
    const size_t N = attr_names.size();
    if (N == 0) {
        std::cerr << "Error: No attributes found in header\n";
        return 1;
    }

    std::vector<Concept> concepts;
    std::map<std::string, int> intent_to_id;

    concepts.reserve(2048);
    // Bottom concept: empty intent, will accumulate all objects
    concepts.push_back({0, std::string(N, '0'), {}});
    intent_to_id[concepts.back().intent] = 0;
    // Top concept: all attributes, empty extent initially
    concepts.push_back({1, std::string(N, '1'), {}});
    intent_to_id[concepts.back().intent] = 1;

    auto t_start = std::chrono::high_resolution_clock::now();

    while (std::getline(csv_stream, line)) {
        line = trim(line);
        if (line.empty()) continue;

        std::stringstream line_ss(line);
        std::string obj_name;
        if (!std::getline(line_ss, obj_name, ';')) continue;
        obj_name = trim(obj_name);

        std::string obj_attrs;
        obj_attrs.reserve(N);
        std::string val;
        size_t count = 0;
        while (count < N && std::getline(line_ss, val, ';')) {
            obj_attrs += (trim(val) == "1" ? '1' : '0');
            ++count;
        }
        while (count < N) { obj_attrs += '0'; ++count; }

        std::map<std::string, int> new_intents;
        size_t current_size = concepts.size();

        for (size_t i = 0; i < current_size; ++i) {
            const Concept& c = concepts[i];
            if (isSubset(c.intent, obj_attrs)) {
                concepts[i].extent.push_back(obj_name);
            } else {
                std::string cand(N, '0');
                for (size_t k = 0; k < N; ++k) {
                    if (c.intent[k] == '1' && obj_attrs[k] == '1') cand[k] = '1';
                }

                if (intent_to_id.find(cand) == intent_to_id.end() && new_intents.find(cand) == new_intents.end()) {
                    int new_id = concepts.size();
                    concepts.push_back({new_id, cand, {obj_name}});
                    new_intents[cand] = new_id;
                } else {
                    int eid = -1;
                    auto it = intent_to_id.find(cand);
                    if (it != intent_to_id.end()) eid = it->second;
                    else eid = new_intents[cand];
                    concepts[eid].extent.push_back(obj_name);
                }
            }
        }

        for (const auto& p : new_intents) {
            intent_to_id[p.first] = p.second;
        }
    }

    std::vector<std::pair<int, int>> edges;
    edges.reserve(concepts.size() * 4);
    size_t n_concepts = concepts.size();
    for (size_t i = 0; i < n_concepts; ++i) {
        for (size_t j = 0; j < n_concepts; ++j) {
            if (i == j) continue;
            // i is superconcept (more attributes), j is subconcept (fewer attributes)
            if (isSubset(concepts[j].intent, concepts[i].intent) && concepts[j].intent != concepts[i].intent) {
                bool intermediate = false;
                for (size_t k = 0; k < n_concepts; ++k) {
                    if (k == i || k == j) continue;
                    if (isSubset(concepts[j].intent, concepts[k].intent) && isSubset(concepts[k].intent, concepts[i].intent)) {
                        intermediate = true;
                        break;
                    }
                }
                if (!intermediate) {
                    edges.emplace_back(concepts[i].id, concepts[j].id);
                }
            }
        }
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> elapsed = t_end - t_start;
    std::cerr << std::fixed << std::setprecision(2) << "CPU Time: " << elapsed.count() << " ms\n";

    dot_stream << "digraph G { rankdir=BT;\n";
    for (const auto& c : concepts) {
        int ic = 0;
        for (char ch : c.intent) if (ch == '1') ++ic;
        int ec = c.extent.size();
        std::string color = (ic == 0 || ic == static_cast<int>(N)) ? "lightblue" : "white";

        dot_stream << c.id << " [shape=record,style=filled,fillcolor=" << color 
                   << ",label=\"{" << c.id << " (I: " << ic << ", E: " << ec << ")|";
        
        for (size_t i = 0; i < N; ++i) {
            if (c.intent[i] == '1') dot_stream << attr_names[i] << "\\n";
        }
        dot_stream << "|";
        for (const auto& obj : c.extent) dot_stream << obj << "\\n";
        dot_stream << "}\"];\n";
    }

    for (const auto& e : edges) {
        dot_stream << e.first << " -> " << e.second << ";\n";
    }
    dot_stream << "}\n";

    return 0;
}