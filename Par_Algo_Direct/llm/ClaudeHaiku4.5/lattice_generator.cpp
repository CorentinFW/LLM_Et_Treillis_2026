#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <set>
#include <map>
#include <string>
#include <algorithm>
#include <bitset>
#include <queue>

/**
 * Formal Concept Analysis (FCA) Lattice Generator
 * 
 * This program computes the complete formal concept lattice from a CSV input file
 * containing binary object-attribute data, and outputs it in Graphviz DOT format.
 * 
 * Algorithm Overview:
 * 1. Parse CSV input to build the object-attribute context
 * 2. Generate all possible attribute subsets (intents)
 * 3. For each intent, compute the extent (objects with all attributes in intent)
 * 4. Keep only lattice elements (closed concepts where intent(extent(I)) = I)
 * 5. Build covering relations by finding immediate successors based on intent containment
 * 6. Output the complete lattice as a directed acyclic graph in DOT format
 * 
 * The lattice is ordered by intent containment:
 * - Bottom node (0): empty intent, all objects
 * - Top node: complete intent, no objects
 * - Edge (I1, E1) -> (I2, E2) exists if I1 ⊂ I2 and there's no intermediate concept
 */

// Structure to represent a concept in the lattice
struct Concept {
    std::set<int> intent;      // Set of attribute indices
    std::set<int> extent;      // Set of object indices
    int id;                    // Unique identifier for the concept
    
    // For comparison and hashing
    bool operator<(const Concept& other) const {
        if (intent.size() != other.intent.size()) 
            return intent.size() < other.intent.size();
        return intent < other.intent;
    }
    
    bool operator==(const Concept& other) const {
        return intent == other.intent && extent == other.extent;
    }
};

// Global data structures
std::vector<std::string> attributes;
std::vector<std::string> objects;
std::vector<std::vector<bool>> context;  // context[obj][attr] = true if obj has attr
std::vector<Concept> lattice;
std::map<std::set<int>, int> concept_map;  // Maps intent to concept id

// Function to read CSV file
// Format: First row contains attribute names separated by ';'
//         Following rows: object_name;attr1;attr2;...
//         where each attr is 0 or 1
bool readCSV(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Unable to open file " << filename << std::endl;
        return false;
    }
    
    std::string line;
    
    // Read header (attributes)
    if (!std::getline(file, line)) {
        std::cerr << "Error: Empty file" << std::endl;
        return false;
    }
    
    std::stringstream ss(line);
    std::string attr;
    int attr_count = 0;
    while (std::getline(ss, attr, ';')) {
        if (!attr.empty()) {
            attributes.push_back(attr);
        }
        attr_count++;
    }
    
    // The first column is empty (object names), so we have attr_count-1 actual attributes
    if (attributes.empty()) {
        std::cerr << "Error: No attributes in file" << std::endl;
        return false;
    }
    
    // Read objects and their attributes
    int row = 0;
    while (std::getline(file, line)) {
        if (line.empty()) continue;
        
        std::vector<bool> obj_attributes;
        std::stringstream ss(line);
        std::string value;
        int col = 0;
        
        while (std::getline(ss, value, ';')) {
            if (col == 0) {
                // First column is object name
                objects.push_back(value);
            } else {
                // Following columns are binary attributes
                obj_attributes.push_back(value == "1");
            }
            col++;
        }
        
        if (obj_attributes.size() != attributes.size()) {
            std::cerr << "Error: Inconsistent number of attributes in row " << row << std::endl;
            return false;
        }
        
        context.push_back(obj_attributes);
        row++;
    }
    
    file.close();
    return true;
}

// Compute extent for a given intent (set of attributes)
// extent(I) = {objects that have ALL attributes in I}
std::set<int> computeExtent(const std::set<int>& intent) {
    std::set<int> extent;
    
    // An object is in the extent if it has ALL attributes in the intent
    for (int obj = 0; obj < objects.size(); obj++) {
        bool has_all = true;
        for (int attr : intent) {
            if (!context[obj][attr]) {
                has_all = false;
                break;
            }
        }
        if (has_all) {
            extent.insert(obj);
        }
    }
    
    return extent;
}

// Compute intent for a given extent (set of objects)
// intent(E) = {attributes shared by ALL objects in E}
std::set<int> computeIntent(const std::set<int>& extent) {
    std::set<int> intent;
    
    if (extent.empty()) {
        // Empty extent means all attributes (all possible objects have all attributes)
        for (int i = 0; i < attributes.size(); i++) {
            intent.insert(i);
        }
        return intent;
    }
    
    // An attribute is in the intent if ALL objects in the extent have it
    for (int attr = 0; attr < attributes.size(); attr++) {
        bool all_have = true;
        for (int obj : extent) {
            if (!context[obj][attr]) {
                all_have = false;
                break;
            }
        }
        if (all_have) {
            intent.insert(attr);
        }
    }
    
    return intent;
}

// Generate all formal concepts (intent, extent) pairs
// Algorithm: Generate all possible attribute subsets and compute their closures
// A formal concept is a pair (I, E) where:
//   - I = intent (set of attributes)
//   - E = extent (set of objects with ALL attributes in I)
//   - Closure property: intent(extent(I)) = I (fixed point)
void generateConcepts() {
    std::map<std::set<int>, std::set<int>> unique_pairs;  // intent -> extent
    
    // Generate all possible intents (2^m possibilities where m = number of attributes)
    int num_attrs = attributes.size();
    
    // For reasonable performance with up to 20-30 attributes
    if (num_attrs > 20) {
        std::cerr << "Warning: Large number of attributes (" << num_attrs 
                  << "), this may take a while" << std::endl;
    }
    
    // Iterate through all possible attribute subsets using bitmask enumeration
    for (long long mask = 0; mask < (1LL << num_attrs); mask++) {
        std::set<int> intent;
        
        // Build intent from bitmask
        for (int i = 0; i < num_attrs; i++) {
            if (mask & (1LL << i)) {
                intent.insert(i);
            }
        }
        
        // Compute extent for this intent: objects having all attributes in intent
        std::set<int> extent = computeExtent(intent);
        
        // Compute closure: compute intent of the extent
        // This ensures we only keep concepts where intent(extent(I)) = I
        std::set<int> closed_intent = computeIntent(extent);
        
        // Store only if it's a valid formal concept (closed)
        if (closed_intent == intent) {
            unique_pairs[intent] = extent;
        }
    }
    
    // Create lattice from unique pairs
    int id = 0;
    for (const auto& pair : unique_pairs) {
        Concept concept;
        concept.intent = pair.first;
        concept.extent = pair.second;
        concept.id = id;
        lattice.push_back(concept);
        concept_map[pair.first] = id;
        id++;
    }
    
    std::cout << "Generated " << lattice.size() << " formal concepts" << std::endl;
}

// Get color for a concept node
std::string getNodeColor(const Concept& concept) {
    // Color lightblue if intent is empty OR extent is empty
    if (concept.intent.empty() || concept.extent.empty()) {
        return "lightblue";
    }
    
    // Color orange if it's a "generator" concept (heuristic: interesting concepts)
    // For now, we'll use lightblue for intent/extent empty, and default color otherwise
    return "";  // Default color
}

// Find immediate successors/predecessors in the lattice
// In FCA: a concept is a successor in the lattice if it has a larger intent
// Edges go from concepts with smaller intent to concepts with larger intent
std::vector<int> findImmediateSuccessors(int concept_id) {
    std::vector<int> successors;
    const Concept& current = lattice[concept_id];
    
    // A concept is an immediate successor if:
    // 1. Its intent is a proper superset of current's intent
    // 2. There's no concept between them (no intermediate intent)
    
    for (int i = 0; i < lattice.size(); i++) {
        if (i == concept_id) continue;
        
        const Concept& candidate = lattice[i];
        
        // Check if candidate's intent is a proper superset of current's intent
        bool is_superset = true;
        for (int attr : current.intent) {
            if (candidate.intent.find(attr) == candidate.intent.end()) {
                is_superset = false;
                break;
            }
        }
        
        if (!is_superset) continue;
        
        // Check if proper superset (has at least one more attribute)
        if (candidate.intent.size() <= current.intent.size()) {
            continue;
        }
        
        // Check if immediate (no concept strictly between them)
        bool is_immediate = true;
        for (int j = 0; j < lattice.size(); j++) {
            if (j == concept_id || j == i) continue;
            
            const Concept& intermediate = lattice[j];
            
            // Check if intermediate is strictly between current and candidate:
            // current.intent ⊂ intermediate.intent ⊂ candidate.intent
            
            bool inter_contains_current = true;
            for (int attr : current.intent) {
                if (intermediate.intent.find(attr) == intermediate.intent.end()) {
                    inter_contains_current = false;
                    break;
                }
            }
            
            bool inter_contained_in_candidate = true;
            for (int attr : intermediate.intent) {
                if (candidate.intent.find(attr) == candidate.intent.end()) {
                    inter_contained_in_candidate = false;
                    break;
                }
            }
            
            if (inter_contains_current && inter_contained_in_candidate &&
                intermediate.intent.size() > current.intent.size() &&
                intermediate.intent.size() < candidate.intent.size()) {
                is_immediate = false;
                break;
            }
        }
        
        if (is_immediate) {
            successors.push_back(i);
        }
    }
    
    return successors;
}

// Write lattice to DOT file
bool writeDOT(const std::string& output_filename) {
    std::ofstream out(output_filename);
    if (!out.is_open()) {
        std::cerr << "Error: Unable to create output file " << output_filename << std::endl;
        return false;
    }
    
    out << "digraph G {\n";
    out << "    rankdir=BT;\n";
    
    // Write all concepts as nodes
    for (const auto& concept : lattice) {
        out << concept.id << " [shape=record,style=filled";
        
        std::string color = getNodeColor(concept);
        if (!color.empty()) {
            out << ",fillcolor=" << color;
        }
        
        out << ",label=\"{" << concept.id << " (I: " << concept.intent.size() 
            << ", E: " << concept.extent.size() << ")|";
        
        // Add attributes to label
        bool first = true;
        for (int attr : concept.intent) {
            if (!first) out << "\\n";
            out << attributes[attr];
            first = false;
        }
        
        out << "|";
        
        // Add objects to label
        first = true;
        for (int obj : concept.extent) {
            if (!first) out << "\\n";
            out << objects[obj];
            first = false;
        }
        
        out << "}\"];\n";
    }
    
    // Write all covering relations as edges
    // In FCA: edge goes from lower concept to higher concept (from smaller intent to larger intent)
    std::set<std::pair<int, int>> edges;
    for (int i = 0; i < lattice.size(); i++) {
        std::vector<int> successors = findImmediateSuccessors(i);
        for (int succ : successors) {
            edges.insert({i, succ});  // i -> succ (from lower to higher in lattice)
        }
    }
    
    for (const auto& edge : edges) {
        out << "    " << edge.first << " -> " << edge.second << "\n";
    }
    
    out << "}\n";
    out.close();
    return true;
}

// Main function
int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <input.csv>" << std::endl;
        return 1;
    }
    
    std::string input_file = argv[1];
    
    // Step 1: Read CSV file
    std::cout << "Reading CSV file: " << input_file << std::endl;
    if (!readCSV(input_file)) {
        return 1;
    }
    
    std::cout << "  Attributes: " << attributes.size() << std::endl;
    std::cout << "  Objects: " << objects.size() << std::endl;
    
    // Step 2: Generate formal concepts
    std::cout << "Generating formal concepts..." << std::endl;
    generateConcepts();
    
    // Step 3: Write output
    std::string output_file = input_file;
    size_t dot_pos = output_file.rfind(".csv");
    if (dot_pos != std::string::npos) {
        output_file = output_file.substr(0, dot_pos) + ".dot";
    } else {
        output_file += ".dot";
    }
    
    std::cout << "Writing DOT file: " << output_file << std::endl;
    if (!writeDOT(output_file)) {
        return 1;
    }
    
    std::cout << "Successfully generated lattice!" << std::endl;
    return 0;
}
