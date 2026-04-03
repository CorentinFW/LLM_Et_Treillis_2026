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
        if (a[i] && !b[i]) return false; // Élément dans a mais pas dans b
        if (b[i] && !a[i]) strict = true;
    }
    return strict;
}

// Compare lexicographiquement : retourne vrai si a > b
inline bool is_lexicographically_greater(const vector<bool>& a, const vector<bool>& b) {
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) return a[i] > b[i]; // 1 > 0 au premier indice différent
    }
    return false; // Égaux ou inférieurs
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
    vector<vector<bool>> attr_extents(num_attrs); // attr_extents[j][i] = 1 si objet i possède attr j

    while (getline(fin, line)) {
        if (line.empty() || line.find_first_not_of(" \t\r\n") == string::npos) continue;
        stringstream ss(line);
        string obj_name;
        getline(ss, obj_name, ';');
        if (obj_name.back() == '\r') obj_name.pop_back();
        obj_names.push_back(obj_name);

        size_t obj_idx = obj_names.size() - 1;
        for (size_t j = 0; j < num_attrs; ++j) {
            string val;
            getline(ss, val, ';');
            if (val.back() == '\r') val.pop_back();
            if (j >= attr_extents.size()) attr_extents.resize(j + 1);
            attr_extents[j].push_back(val == "1");
        }
    }
    size_t num_objs = obj_names.size();

    // Fonction de fermeture : calcule l'intention fermée à partir d'une intention candidate
    // Closure(X) = (X')' où X' = intersection des extensions des attributs dans X
    auto closure = [&](const vector<bool>& intent) -> vector<bool> {
        vector<bool> extent(num_objs, true);
        for (size_t a = 0; a < num_attrs; ++a) {
            if (intent[a]) {
                for (size_t o = 0; o < num_objs; ++o) extent[o] &= attr_extents[a][o];
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

    auto compute_extent = [&](const vector<bool>& intent) -> vector<bool> {
        vector<bool> extent(num_objs, true);
        for (size_t a = 0; a < num_attrs; ++a) {
            if (intent[a]) {
                for (size_t o = 0; o < num_objs; ++o) extent[o] &= attr_extents[a][o];
            }
        }
        return extent;
    };

    // 2. Calcul du treillis via NextClosure (Ganter)
    // Génère les intentions fermées dans l'ordre lexicographique sans récursion ni backtracking.
    // Principe : partir de A (actuellement fermée). Chercher le plus grand indice i tel que
    // m_i ∉ A. Construire B = (A ∩ {m < m_i}) ∪ {m_i}. Fermer B. Si C = closure(B) >_lex A,
    // alors C est le prochain concept. Cela garantit une visite unique de chaque concept fermé.
    
    auto start_time = chrono::high_resolution_clock::now();

    vector<Concept> concepts;
    vector<bool> A(num_attrs, false);
    vector<bool> closed = closure(A);
    A = closed;
    concepts.push_back({A, compute_extent(A)});

    while (true) {
        bool found_next = false;
        // Parcours décroissant des attributs pour trouver le successeur lexicographique
        for (int i = (int)num_attrs - 1; i >= 0; --i) {
            if (!A[i]) {
                vector<bool> B = A;
                for (int j = i + 1; j < (int)num_attrs; ++j) B[j] = false; // Masque les bits supérieurs
                B[i] = true; // Ajoute l'attribut courant
                vector<bool> C = closure(B);
                if (is_lexicographically_greater(C, A)) {
                    A = C;
                    concepts.push_back({A, compute_extent(A)});
                    found_next = true;
                    break;
                }
            }
        }
        if (!found_next) break; // Tous les concepts ont été énumérés
    }

    // 3. Calcul de la relation de couverture (cover relation)
    // C_j couvre C_i si extent_i ⊂ extent_j et aucun concept C_k n'existe tel que extent_i ⊂ extent_k ⊂ extent_j.
    vector<pair<int, int>> edges;
    size_t C = concepts.size();
    for (size_t j = 0; j < C; ++j) {
        vector<int> parents;
        for (size_t i = 0; i < C; ++i) {
            if (i == j) continue;
            // extent_i ⊂ extent_j => i est au-dessus de j dans le treillis
            if (is_proper_subset(concepts[i].extent, concepts[j].extent))
                parents.push_back(i);
        }
        // Garder uniquement les maximaux (ceux non strictement contenus dans un autre parent candidat)
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

    // Sortie temps CPU
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

        // Construction des labels avec sauts de ligne
        string intent_str, extent_str;
        bool first = true;
        for (size_t a = 0; a < num_attrs; ++a) {
            if (concepts[id].intent[a]) {
                if (!first) intent_str += "\\n";
                intent_str += attr_names[a];
                first = false;
            }
        }
        first = true;
        for (size_t o = 0; o < num_objs; ++o) {
            if (concepts[id].extent[o]) {
                if (!first) extent_str += "\\n";
                extent_str += obj_names[o];
                first = false;
            }
        }

        // Format: {ID (I: x, E: y)|attrs|objs}
        fout << "    " << id << " [shape=record,style=filled" << color_attr
             << ",label=\"{" << id << " (I: " << I_cnt << ", E: " << E_cnt << ")|"
             << intent_str << "\\n|" << extent_str << "\\n}\"];\n";
    }

    for (const auto& e : edges) {
        fout << "    " << e.first << " -> " << e.second << "\n";
    }
    fout << "}\n";

    return 0;
}