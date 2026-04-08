#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>
#include <chrono>
#include <map>
#include <set>

using namespace std;

// Représentation binaire d'un ensemble (via vector<bool> pour de plus grandes tailles que 64)
typedef vector<bool> BitSet;

// Structure pour stocker le contexte formel
struct FormalContext {
    vector<string> objects;
    vector<string> attributes;
    vector<BitSet> table; // table[obj_idx][attr_idx]
};

// Structure représentant un concept formel
struct Concept {
    int id;
    BitSet extent;
    BitSet intent;
    
    // Pour l'affichage des labels réduits dans le diagramme de Hasse
    vector<string> own_objects;
    vector<string> own_attributes;

    bool operator==(const Concept& other) const {
        return extent == other.extent && intent == other.intent;
    }
};

// --- Fonctions Utilitaires sur les BitSets ---
BitSet intersectBitSets(const BitSet& a, const BitSet& b) {
    BitSet res(a.size(), false);
    for (size_t i = 0; i < a.size(); ++i) {
        res[i] = a[i] && b[i];
    }
    return res;
}

bool isSubset(const BitSet& a, const BitSet& b) {
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] && !b[i]) return false;
    }
    return true;
}

int countBits(const BitSet& a) {
    int count = 0;
    for (bool bit : a) if (bit) count++;
    return count;
}

// --- Opérateurs de dérivation (Polaires) ---
// Retourne l'intension d'un ensemble d'objets (A')
BitSet deriveObjects(const FormalContext& ctx, const BitSet& objectsSet) {
    BitSet intent(ctx.attributes.size(), true);
    bool any_obj = false;
    for (size_t i = 0; i < objectsSet.size(); ++i) {
        if (objectsSet[i]) {
            any_obj = true;
            intent = intersectBitSets(intent, ctx.table[i]);
        }
    }
    if (!any_obj) {
        // L'intension de l'ensemble vide d'objets est l'ensemble de tous les attributs
        return BitSet(ctx.attributes.size(), true);
    }
    return intent;
}

// Retourne l'extension d'un ensemble d'attributs (B')
BitSet deriveAttributes(const FormalContext& ctx, const BitSet& attributesSet) {
    BitSet extent(ctx.objects.size(), true);
    bool any_attr = false;
    for (size_t num_obj = 0; num_obj < ctx.objects.size(); ++num_obj) {
        bool has_all_attrs = true;
        for (size_t j = 0; j < attributesSet.size(); ++j) {
            if (attributesSet[j]) {
                any_attr = true;
                if (!ctx.table[num_obj][j]) {
                    has_all_attrs = false;
                    break;
                }
            }
        }
        extent[num_obj] = has_all_attrs;
    }
    if (!any_attr) {
        // L'extension de l'ensemble vide d'attributs est l'ensemble de tous les objets
        return BitSet(ctx.objects.size(), true);
    }
    return extent;
}

// --- Parseur de CSV ---
bool parseCSV(const string& filename, FormalContext& ctx) {
    ifstream file(filename);
    if (!file.is_open()) {
        cerr << "Erreur: Impossible d'ouvrir " << filename << endl;
        return false;
    }

    string line;
    if (getline(file, line)) {
        stringstream ss(line);
        string cell;
        getline(ss, cell, ';'); // Ignorer la première case vide

        while (getline(ss, cell, ';')) {
            // Nettoyer les retours chariots potentiels (CRLF)
            cell.erase(remove(cell.begin(), cell.end(), '\r'), cell.end());
            cell.erase(remove(cell.begin(), cell.end(), '\n'), cell.end());
            if(!cell.empty()) ctx.attributes.push_back(cell);
        }
    }

    while (getline(file, line)) {
        if(line.empty()) continue;
        stringstream ss(line);
        string cell;
        
        getline(ss, cell, ';');
        cell.erase(remove(cell.begin(), cell.end(), '\r'), cell.end());
        ctx.objects.push_back(cell);

        BitSet row(ctx.attributes.size(), false);
        size_t attr_idx = 0;
        while (getline(ss, cell, ';') && attr_idx < ctx.attributes.size()) {
            if (cell == "1") {
                row[attr_idx] = true;
            }
            attr_idx++;
        }
        ctx.table.push_back(row);
    }

    file.close();
    return true;
}

// --- Implémentation de l'Algo Direct (Fermeture "d'une seule traite") ---
void buildConceptLattice(const FormalContext& ctx, vector<Concept>& concepts, vector<pair<int, int>>& hasseEdges) {
    // 1. Génération globale & directe de tous les concepts (Intersection des intensions)
    // On commence par générer l'ensemble des concepts en collectant toutes les intensions possibles
    vector<BitSet> intents;
    
    // Intension pour le concept Top (l'intension de tous les objets)
    BitSet all_objs(ctx.objects.size(), true);
    intents.push_back(deriveObjects(ctx, all_objs));

    for (size_t i = 0; i < ctx.objects.size(); ++i) {
        BitSet single_obj(ctx.objects.size(), false);
        single_obj[i] = true;
        BitSet obj_intent = deriveObjects(ctx, single_obj);
        
        // Prendre la fermeture par intersection avec les intensions existantes
        size_t current_size = intents.size();
        for (size_t j = 0; j < current_size; ++j) {
            BitSet intersection = intersectBitSets(intents[j], obj_intent);
            
            // Vérifier si cette intension n'est pas déjà découverte
            bool exists = false;
            for (const auto& existing : intents) {
                if (existing == intersection) {
                    exists = true;
                    break;
                }
            }
            if (!exists) {
                intents.push_back(intersection);
            }
        }
        
        // Ajouter l'intension d'objet individuel si elle est nouvelle
        bool exists = false;
        for (const auto& existing : intents) {
            if (existing == obj_intent) {
                exists = true; break;
            }
        }
        if (!exists) {
            intents.push_back(obj_intent);
        }
    }

    // Concept Bottom (tous les attributs)
    BitSet all_attrs(ctx.attributes.size(), true);
    bool bot_exists = false;
    for (const auto& existing : intents) {
        if (existing == all_attrs) { bot_exists = true; break; }
    }
    if (!bot_exists) intents.push_back(all_attrs);

    // Initialisation et Peuplement de la liste des concepts
    // Pour chaque intension trouvée, on calcule l'extension finale
    for (size_t i = 0; i < intents.size(); ++i) {
        Concept c;
        c.id = static_cast<int>(i);
        c.intent = intents[i];
        c.extent = deriveAttributes(ctx, c.intent);
        concepts.push_back(c);
    }

    // 2. Création de la relation de couverture (Arêtes du diagramme de Hasse)
    for (size_t i = 0; i < concepts.size(); ++i) {
        for (size_t j = 0; j < concepts.size(); ++j) {
            if (i == j) continue;
            // Une arête de j à i existe si j <= i (en extention) et qu'il n'y a pas d'intermédiaire
            // c'est à dire l'extension de j est un sous-ensemble strict de i
            if (isSubset(concepts[j].extent, concepts[i].extent)) {
                bool is_direct_child = true;
                // On vérifie s'il n'y a pas de concept K entre les deux
                for (size_t k = 0; k < concepts.size(); ++k) {
                    if (k == i || k == j) continue;
                    if (isSubset(concepts[j].extent, concepts[k].extent) && 
                        isSubset(concepts[k].extent, concepts[i].extent)) {
                        is_direct_child = false;
                        break;
                    }
                }
                if (is_direct_child) {
                    // On enregistre l'arête (relation: concept enfant -> concept parent)
                    hasseEdges.push_back(make_pair(concepts[j].id, concepts[i].id));
                }
            }
        }
    }

    // 3. Calcul de l'affichage réduit (Attributs propres & Objets propres)
    for (auto& c : concepts) {
        for (size_t obj_idx = 0; obj_idx < ctx.objects.size(); ++obj_idx) {
            if (c.extent[obj_idx]) {
                // Si l'objet n'appartient à aucun des enfants de C, alors c'est le concept "créateur" de l'objet
                bool is_own = true;
                for (auto edge : hasseEdges) {
                    if (edge.second == c.id) { // c est le parent
                        if (concepts[edge.first].extent[obj_idx]) {
                            is_own = false;
                            break;
                        }
                    }
                }
                if (is_own) c.own_objects.push_back(ctx.objects[obj_idx]);
            }
        }

        for (size_t attr_idx = 0; attr_idx < ctx.attributes.size(); ++attr_idx) {
            if (c.intent[attr_idx]) {
                // Si l'attribut n'appartient à aucun des parents de C, alors c'est le concept "créateur" de l'attribut
                bool is_own = true;
                for (auto edge : hasseEdges) {
                    if (edge.first == c.id) { // c est l'enfant
                        if (concepts[edge.second].intent[attr_idx]) {
                            is_own = false;
                            break;
                        }
                    }
                }
                if (is_own) c.own_attributes.push_back(ctx.attributes[attr_idx]);
            }
        }
    }
}

// --- Exporteur DOT (Graphviz) ---
void exportToDOT(const string& filename, const vector<Concept>& concepts, const vector<pair<int, int>>& edges) {
    ofstream file(filename);
    if (!file.is_open()) {
        cerr << "Erreur: Impossible de créer " << filename << endl;
        return;
    }

    file << "digraph G {\n";
    file << "    rankdir=BT;\n";

    for (const auto& c : concepts) {
        string attrs_str = "";
        for (const auto& a : c.own_attributes) attrs_str += a + "\\n";
        
        string objs_str = "";
        for (const auto& o : c.own_objects) objs_str += o + "\\n";

        // Définition conditionnelle du style du noeud
        string style = "shape=record,style=filled";
        if(c.own_attributes.empty() && c.own_objects.empty()) {
             style += ",fillcolor=lightblue";
        } else if (!c.own_attributes.empty() && !c.own_objects.empty()) {
             style += ",fillcolor=orange";
        }

        int i_count = countBits(c.intent);
        int e_count = countBits(c.extent);

        file << "    " << c.id << " [" << style << ",label=\"{" 
             << c.id << " (I: " << i_count << ", E: " << e_count << ")|"
             << attrs_str << "|" << objs_str << "}\"];\n";
    }

    for (const auto& edge : edges) {
        file << "    " << edge.first << " -> " << edge.second << ";\n";
    }

    file << "}\n";
    file.close();
}


int main(int argc, char* argv[]) {
    string inFile = "Format/Animals11.csv";
    string outFile = "Format/Animals11.dot";

    if (argc >= 3) {
        inFile = argv[1];
        outFile = argv[2];
    }

    FormalContext ctx;
    
    cout << "Chargement de la base de contexte depuis " << inFile << "..." << endl;
    if (!parseCSV(inFile, ctx)) return EXIT_FAILURE;

    cout << "  - > Objets: " << ctx.objects.size() 
         << ", Attributs: " << ctx.attributes.size() << endl;

    vector<Concept> concepts;
    vector<pair<int, int>> hasseEdges;

    // ----- DÉMARRAGE DU CHRONO -----
    auto start_time = chrono::high_resolution_clock::now();

    // L'approche "d'une seule traite" qui génére le Treillis et le graphe Hasse
    buildConceptLattice(ctx, concepts, hasseEdges);

    // ----- ARRÊT DU CHRONO -----
    auto end_time = chrono::high_resolution_clock::now();
    auto duration_ms = chrono::duration_cast<chrono::milliseconds>(end_time - start_time);
    auto duration_us = chrono::duration_cast<chrono::microseconds>(end_time - start_time);

    cout << "\n=============================================\n";
    cout << "[INFO] Algorithme direct de Treillis de Concepts terminé." << endl;
    cout << "  - > Concepts générés : " << concepts.size() << endl;
    cout << "  - > Arêtes (Hasse)   : " << hasseEdges.size() << endl;
    cout << "  - > Temps algorithme : " << duration_ms.count() << " ms (" 
         << duration_us.count() << " microsecondes)" << endl;
    cout << "=============================================\n\n";

    cout << "Exportation du treillis aux conventions de couleur (Labels Réduits) :" << endl;
    exportToDOT(outFile, concepts, hasseEdges);
    cout << "  - > Fichier DOT généré dans : " << outFile << endl;

    return EXIT_SUCCESS;
}