#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>
#include <chrono>
#include <cmath>

using namespace std;

// Structure représentant un concept formel (intention/extension)
struct Concept {
    vector<bool> intent;
    vector<bool> extent;
};

// Vérifie si a est un sous-ensemble strict de b
inline bool is_proper_subset(const vector<bool>& a, const vector<bool>& b) {
    bool strict = false;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] && !b[i]) return false;
        if (b[i] && !a[i]) strict = true;
    }
    return strict;
}

// Compare lexicographiquement : retourne vrai si a > b
inline bool is_lexicographically_greater(const vector<bool>& a, const vector<bool>& b) {
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) return a[i] > b[i];
    }
    return false;
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        cerr << "Usage: " << argv[0] << " input.csv output.dot\n";
        return 1;
    }

    ifstream fin(argv[1]);
    if (!fin) { cerr << "Erreur: impossible d'ouvrir " << argv[1] << "\n"; return 1; }

    // 1. Parsing CSV
    vector<string> attr_names;
    string line;
    if (getline(fin, line)) {
        stringstream ss(line);
        string token;
        while (getline(ss, token, ';')) {
            if (!token.empty()) {
                if (token.back() == '\r') token.pop_back();
                attr_names.push_back(token);
            }
        }
    }
    size_t num_attrs = attr_names.size();
    if (num_attrs == 0) { cerr << "Erreur: aucun attribut trouvé\n"; return 1; }

    vector<string> obj_names;
    vector<vector<bool>> attr_extents(num_attrs);

    while (getline(fin, line)) {
        if (line.empty() || line.find_first_not_of(" \t\r\n") == string::npos) continue;
        stringstream ss(line);
        string obj_name;
        getline(ss, obj_name, ';');
        if (!obj_name.empty() && obj_name.back() == '\r') obj_name.pop_back();
        obj_names.push_back(obj_name);

        size_t obj_idx = obj_names.size() - 1;
        for (size_t j = 0; j < num_attrs; ++j) {
            string val;
            getline(ss, val, ';');
            if (!val.empty() && val.back() == '\r') val.pop_back();
            if (j >= attr_extents.size()) attr_extents.resize(j + 1);
            attr_extents[j].push_back(val == "1");
        }
    }
    size_t num_objs = obj_names.size();

    // Fonction de fermeture : closure(X) = (X')'
    auto closure = [&](const vector<bool>& intent) -> vector<bool> {
        vector<bool> extent(num_objs, true);
        for (size_t a = 0; a < num_attrs; ++a) {
            if (intent[a]) {
                for (size_t o = 0; o < num_objs; ++o) {
                    if (!attr_extents[a][o]) extent[o] = false;
                }
            }
        }
        vector<bool> new_intent(num_attrs, false);
        for (size_t a = 0; a < num_attrs; ++a) {
            bool shared = true;
            for (size_t o = 0; o < num_objs; ++o) {
                if (extent[o] && !attr_extents[a][o]) { shared = false; break; }
            }
            new_intent[a] = shared;
        }
        return new_intent;
    };

    // Calcul d'extension simple (sans recomputer l'intention)
    auto compute_extent = [&](const vector<bool>& intent) -> vector<bool> {
        vector<bool> extent(num_objs, true);
        for (size_t a = 0; a < num_attrs; ++a) {
            if (intent[a]) {
                for (size_t o = 0; o < num_objs; ++o) {
                    if (!attr_extents[a][o]) extent[o] = false;
                }
            }
        }
        return extent;
    };

    // 2. Calcul du treillis via NextClosure (Ganter)
    // Algorithme "one-pass" : parcours itératif de l'espace lexicographique des intentions fermées.
    // Principe : À partir de l'intention fermée courante A, on cherche le plus grand indice i tel que m_i ∉ A.
    // On construit B = (A ∩ {m < m_i}) ∪ {m_i}, on ferme B. Si closure(B) >_lex A, c'est le concept suivant.
    auto start_time = chrono::high_resolution_clock::now();

    vector<Concept> concepts;
    vector<bool> A(num_attrs, false);
    A = closure(A);
    concepts.push_back({A, compute_extent(A)});

    while (true) {
        bool found_next = false;
        for (int i = (int)num_attrs - 1; i >= 0; --i) {
            if (!A[i]) {
                vector<bool> B = A;
                for (int j = i + 1; j < (int)num_attrs; ++j) B[j] = false;
                B[i] = true;
                vector<bool> C = closure(B);
                if (is_lexicographically_greater(C, A)) {
                    A = C;
                    concepts.push_back({A, compute_extent(A)});
                    found_next = true;
                    break;
                }
            }
        }
        if (!found_next) break;
    }

    // 3. Calcul de la relation de couverture
    vector<pair<int, int>> edges;
    size_t C = concepts.size();
    for (size_t j = 0; j < C; ++j) {
        vector<int> parents;
        for (size_t i = 0; i < C; ++i) {
            if (i == j) continue;
            if (is_proper_subset(concepts[i].extent, concepts[j].extent))
                parents.push_back((int)i);
        }
        for (size_t p = 0; p < parents.size(); ++p) {
            bool is_cover = true;
            for (size_t q = 0; q < parents.size(); ++q) {
                if (p == q) continue;
                if (is_proper_subset(concepts[parents[p]].extent, concepts[parents[q]].extent)) {
                    is_cover = false; break;
                }
            }
            if (is_cover) edges.emplace_back((int)j, parents[p]);
        }
    }

    auto end_time = chrono::high_resolution_clock::now();
    long long ms = llround(chrono::duration<double, milli>(end_time - start_time).count());
    cout << "Temps CPU calcul treillis : " << ms << " ms\n";

    // 4. Export DOT strict
    ofstream fout(argv[2]);
    if (!fout) { cerr << "Erreur: impossible d'écrire " << argv[2] << "\n"; return 1; }

    fout << "digraph G { rankdir=BT;\n";
    for (size_t id = 0; id < C; ++id) {
        int I_cnt = 0; for (bool b : concepts[id].intent) if (b) I_cnt++;
        int E_cnt = 0; for (bool b : concepts[id].extent) if (b) E_cnt++;

        string color_attr = "";
        if (I_cnt == 0 || E_cnt == 0) color_attr = ",fillcolor=lightblue";
        else if (I_cnt >= 5 && E_cnt >= 3) color_attr = ",fillcolor=orange";

        string intent_str, extent_str;
        bool first = true;
        for (size_t a = 0; a < num_attrs; ++a) {
            if (concepts[id].intent[a]) {
                if (!first) intent_str += "\n";
                intent_str += attr_names[a];
                first = false;
            }
        }
        first = true;
        for (size_t o = 0; o < num_objs; ++o) {
            if (concepts[id].extent[o]) {
                if (!first) extent_str += "\n";
                extent_str += obj_names[o];
                first = false;
            }
        }

        string label = "{" + to_string(id) + " (I: " + to_string(I_cnt) + ", E: " + to_string(E_cnt) + ")|";
        if (!intent_str.empty()) label += intent_str + "\n";
        label += "|";
        if (!extent_str.empty()) label += extent_str + "\n";
        label += "}";

        fout << "    " << id << " [shape=record,style=filled" << color_attr << ",label=\"" << label << "\"];\n";
    }

    for (const auto& e : edges) {
        fout << "    " << e.first << " -> " << e.second << "\n";
    }
    fout << "}\n";

    return 0;
}