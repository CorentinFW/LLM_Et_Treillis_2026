#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <set>
#include <map>
#include <algorithm>
#include <chrono>
#include <numeric>

// Représente un concept avec son extension (objets) et son intention (attributs)
struct Concept {
    std::set<int> extent;
    std::set<int> intent;
    int id;

    bool operator<(const Concept& other) const {
        return intent < other.intent;
    }
};

// Fonction pour formater un ensemble en chaîne de caractères pour l'affichage
template<typename T>
std::string set_to_string(const std::set<T>& s, const std::vector<std::string>& names) {
    std::stringstream ss;
    ss << "{";
    bool first = true;
    for (const auto& item : s) {
        if (!first) {
            ss << ", ";
        }
        if (item < names.size()) {
            ss << names[item];
        }
        first = false;
    }
    ss << "}";
    return ss.str();
}

// Dérivation de l'intention (attributs communs) à partir d'un ensemble d'objets
std::set<int> derive_intent(const std::set<int>& objects, const std::vector<std::vector<bool>>& context, int num_attributes) {
    if (objects.empty()) {
        std::set<int> all_attributes;
        for (int i = 0; i < num_attributes; ++i) {
            all_attributes.insert(i);
        }
        return all_attributes;
    }

    std::set<int> common_attributes;
    int first_obj = *objects.begin();
    for (int i = 0; i < num_attributes; ++i) {
        if (context[first_obj][i]) {
            common_attributes.insert(i);
        }
    }

    for (int obj_idx : objects) {
        std::set<int> to_remove;
        for (int attr_idx : common_attributes) {
            if (!context[obj_idx][attr_idx]) {
                to_remove.insert(attr_idx);
            }
        }
        for (int attr_idx : to_remove) {
            common_attributes.erase(attr_idx);
        }
    }
    return common_attributes;
}

// Dérivation de l'extension (objets communs) à partir d'un ensemble d'attributs
std::set<int> derive_extent(const std::set<int>& attributes, const std::vector<std::vector<bool>>& context, int num_objects) {
    std::set<int> common_objects;
    for (int i = 0; i < num_objects; ++i) {
        bool has_all_attributes = true;
        for (int attr_idx : attributes) {
            if (!context[i][attr_idx]) {
                has_all_attributes = false;
                break;
            }
        }
        if (has_all_attributes) {
            common_objects.insert(i);
        }
    }
    return common_objects;
}

// Algorithme AddIntent pour construire le treillis de concepts de manière incrémentale
void add_intent(std::set<int> intent, int object_id,
                std::set<Concept>& lattice,
                const std::vector<std::vector<bool>>& context,
                int num_objects, int num_attributes) {

    std::set<Concept> new_concepts;
    std::set<Concept> concepts_to_remove;

    for (const auto& concept : lattice) {
        std::set<int> intersection;
        std::set_intersection(intent.begin(), intent.end(),
                              concept.intent.begin(), concept.intent.end(),
                              std::inserter(intersection, intersection.begin()));

        bool is_subconcept = true;
        for (const auto& existing_concept : lattice) {
            if (intersection != existing_concept.intent) {
                 std::set<int> temp_intersection;
                 std::set_intersection(intersection.begin(), intersection.end(),
                                      existing_concept.intent.begin(), existing_concept.intent.end(),
                                      std::inserter(temp_intersection, temp_intersection.begin()));
                if(temp_intersection == intersection && intersection.size() < existing_concept.intent.size()){
                    is_subconcept = false;
                    break;
                }
            }
        }

        if (is_subconcept) {
            auto it = std::find_if(new_concepts.begin(), new_concepts.end(), [&](const Concept& c){
                return c.intent == intersection;
            });
             if (it == new_concepts.end()) {
                Concept new_concept;
                new_concept.intent = intersection;
                new_concept.extent = derive_extent(new_concept.intent, context, num_objects);
                new_concepts.insert(new_concept);
            }
        }
    }

    for(const auto& c : new_concepts){
        lattice.insert(c);
    }
}


// Fonction principale
int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <input_csv_file> <output_dot_file>" << std::endl;
        return 1;
    }

    std::string input_filename = argv[1];
    std::string output_filename = argv[2];

    std::ifstream file(input_filename);
    if (!file.is_open()) {
        std::cerr << "Error: Could not open input file " << input_filename << std::endl;
        return 1;
    }

    // Lecture des données CSV
    std::vector<std::string> attributes;
    std::vector<std::string> objects;
    std::vector<std::vector<bool>> context;
    std::string line;

    // Lire l'en-tête (attributs)
    if (std::getline(file, line)) {
        std::stringstream ss(line);
        std::string cell;
        std::getline(ss, cell, ','); // Ignorer la première cellule vide
        while (std::getline(ss, cell, ',')) {
            // Supprimer les retours à la ligne potentiels
            cell.erase(std::remove(cell.begin(), cell.end(), '\r'), cell.end());
            cell.erase(std::remove(cell.begin(), cell.end(), '\n'), cell.end());
            attributes.push_back(cell);
        }
    }

    // Lire les objets et la matrice de contexte
    while (std::getline(file, line)) {
        std::stringstream ss(line);
        std::string object_name;
        std::getline(ss, object_name, ',');
        objects.push_back(object_name);

        std::vector<bool> row;
        std::string cell;
        while (std::getline(ss, cell, ',')) {
            row.push_back(cell == "1");
        }
        context.push_back(row);
    }
    file.close();

    int num_objects = objects.size();
    int num_attributes = attributes.size();

    // Début de la mesure du temps
    auto start_time = std::chrono::high_resolution_clock::now();

    // Construction du treillis
    std::set<Concept> lattice;

    // Concept bottom : tous les objets, intention vide (dérivée)
    std::set<int> all_objects_set;
    for(int i=0; i<num_objects; ++i) all_objects_set.insert(i);
    Concept bottom_concept;
    bottom_concept.extent = all_objects_set;
    bottom_concept.intent = derive_intent(bottom_concept.extent, context, num_attributes);
    lattice.insert(bottom_concept);

    // Concept top : tous les attributs, extension vide (dérivée)
    std::set<int> all_attributes_set;
    for(int i=0; i<num_attributes; ++i) all_attributes_set.insert(i);
    Concept top_concept;
    top_concept.intent = all_attributes_set;
    top_concept.extent = derive_extent(top_concept.intent, context, num_objects);
    lattice.insert(top_concept);

    // Ajout incrémental de chaque objet
    for (int i = 0; i < num_objects; ++i) {
        std::set<int> object_intent;
        for (int j = 0; j < num_attributes; ++j) {
            if (context[i][j]) {
                object_intent.insert(j);
            }
        }
        add_intent(object_intent, i, lattice, context, num_objects, num_attributes);
    }
    
    // Fin de la mesure du temps
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::micro> cpu_time = end_time - start_time;

    std::cout << "CPU time for lattice construction: " << cpu_time.count() << " microseconds" << std::endl;

    // Assignation des IDs et création de la map pour le .dot
    std::vector<Concept> concept_list(lattice.begin(), lattice.end());
    std::map<std::set<int>, int> intent_to_id;
    for(size_t i = 0; i < concept_list.size(); ++i) {
        concept_list[i].id = i;
        intent_to_id[concept_list[i].intent] = i;
    }

    // Génération du fichier .dot
    std::ofstream dot_file(output_filename);
    if (!dot_file.is_open()) {
        std::cerr << "Error: Could not open output file " << output_filename << std::endl;
        return 1;
    }

    dot_file << "digraph ConceptLattice {" << std::endl;
    dot_file << "    rankdir=BT;" << std::endl;

    // Définition des nœuds
    for (const auto& concept : concept_list) {
        dot_file << "    " << concept.id << " [label=<"
                 << "<B>" << set_to_string(concept.extent, objects) << "</B><BR/>"
                 << set_to_string(concept.intent, attributes)
                 << ">];" << std::endl;
    }

    // Définition des arêtes
    for (const auto& concept_i : concept_list) {
        for (const auto& concept_j : concept_list) {
            if (concept_i.id == concept_j.id) continue;

            // Si l'intention de i est un sous-ensemble strict de l'intention de j
            if (std::includes(concept_j.intent.begin(), concept_j.intent.end(),
                              concept_i.intent.begin(), concept_i.intent.end()) &&
                concept_i.intent.size() < concept_j.intent.size()) {
                
                bool is_direct_successor = true;
                // Vérifier s'il existe un concept k intermédiaire
                for (const auto& concept_k : concept_list) {
                    if (concept_k.id == concept_i.id || concept_k.id == concept_j.id) continue;
                    
                    if (std::includes(concept_k.intent.begin(), concept_k.intent.end(), concept_i.intent.begin(), concept_i.intent.end()) &&
                        std::includes(concept_j.intent.begin(), concept_j.intent.end(), concept_k.intent.begin(), concept_k.intent.end()) &&
                        concept_i.intent.size() < concept_k.intent.size() && concept_k.intent.size() < concept_j.intent.size()) {
                        is_direct_successor = false;
                        break;
                    }
                }

                if (is_direct_successor) {
                    dot_file << "    " << concept_i.id << " -> " << concept_j.id << ";" << std::endl;
                }
            }
        }
    }

    dot_file << "}" << std::endl;
    dot_file.close();

    std::cout << "Lattice has " << concept_list.size() << " concepts." << std::endl;
    std::cout << "DOT file '" << output_filename << "' generated successfully." << std::endl;

    return 0;
}
