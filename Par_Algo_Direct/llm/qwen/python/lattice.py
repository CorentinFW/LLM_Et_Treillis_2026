#!/usr/bin/env python3
"""
Formal Concept Lattice Generator (NextClosure Algorithm)
--------------------------------------------------------
Lit un contexte formel binaire (CSV), calcule le treillis de concepts formels,
exporte le diagramme de Hasse au format Graphviz (.dot) et mesure le temps CPU.
Conforme aux spécifications FCA, PEP 8, et contraintes d'exécution imposées.
"""

import sys
import csv
import time
import os
from typing import List, Set, Tuple, Dict, Optional


def read_and_validate_csv(filepath: str) -> Tuple[List[str], List[str], List[List[int]]]:
    """
    Lit et valide le fichier CSV.
    Retourne: (noms_objets, noms_attributs, matrice_contexte)
    Lève ValueError si le format ou les données sont invalides.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Le fichier '{filepath}' est introuvable.")

    objects = []
    attributes = []
    context = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        
        # Lecture de l'en-tête
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("Fichier CSV vide.")
            
        # La première cellule est souvent vide ou contient un placeholder. On ignore.
        attributes = [a.strip() for a in header[1:] if a.strip()]
        if not attributes:
            raise ValueError("Aucun attribut trouvé dans l'en-tête.")

        num_attrs = len(attributes)

        for line_num, row in enumerate(reader, start=2):
            if not row or all(c.strip() == "" for c in row):
                continue  # Ligne vide ignorée
                
            obj_name = row[0].strip()
            if not obj_name:
                raise ValueError(f"Ligne {line_num}: nom d'objet manquant.")
            objects.append(obj_name)

            # Extraction et validation des valeurs binaires
            values = []
            raw_vals = row[1:]
            if len(raw_vals) < num_attrs:
                raise ValueError(f"Ligne {line_num}: nombre d'attributs insuffisant.")
                
            for i, val in enumerate(raw_vals[:num_attrs]):
                val = val.strip()
                if val not in ("0", "1"):
                    raise ValueError(f"Ligne {line_num}, attribut {i}: valeur '{val}' invalide (attendu 0 ou 1).")
                values.append(int(val))
            context.append(values)

    if not objects:
        raise ValueError("Aucun objet trouvé dans le contexte.")

    return objects, attributes, context


def precompute_mappings(context: List[List[int]], num_attrs: int) -> List[Set[int]]:
    """
    Précalcule pour chaque attribut l'ensemble des objets qui le possèdent.
    Optimise les opérations de dérivation ultérieures.
    """
    num_objs = len(context)
    attr_to_objs: List[Set[int]] = [set() for _ in range(num_attrs)]
    for obj_idx, row in enumerate(context):
        for attr_idx, val in enumerate(row):
            if val == 1:
                attr_to_objs[attr_idx].add(obj_idx)
    return attr_to_objs


def derive_and_close(
    attr_indices: Set[int],
    attr_to_objs: List[Set[int]],
    all_obj_indices: Set[int],
    all_attr_indices: Set[int]
) -> Tuple[Set[int], Set[int]]:
    """
    Calcul de la fermeture (intention, extension) d'un ensemble d'attributs.
    Étape mathématique clé : 
      1. Dérivation vers les objets : A' = ⋂_{m∈A} m'
      2. Dérivation inverse vers les attributs : A'' = {m ∈ M | A' ⊆ m'}
    Retourne (intention_fermée, extension_fermée)
    """
    # 1. Calcul de l'extension (intersection des objets possédant tous les attributs)
    if not attr_indices:
        extent = all_obj_indices.copy()
    else:
        it = iter(attr_indices)
        extent = attr_to_objs[next(it)].copy()
        for a in it:
            extent.intersection_update(attr_to_objs[a])
            if not extent:
                break

    # 2. Calcul de l'intention fermée depuis l'extension
    intent = set()
    for m in all_attr_indices:
        if extent.issubset(attr_to_objs[m]):
            intent.add(m)
    return intent, extent


def generate_lattice(
    num_attrs: int,
    attr_to_objs: List[Set[int]],
    all_obj_indices: Set[int],
    all_attr_indices: Set[int]
) -> List[Tuple[Set[int], Set[int]]]:
    """
    Algorithme NextClosure (Ganter, 1984) : génération itérative de tous les concepts
    dans l'ordre lectic, sans récursion ni recalcul superflu.
    """
    concepts: List[Tuple[Set[int], Set[int]]] = []
    
    # Concept initial : fermeture de l'ensemble vide (borne inférieure)
    current_intent, current_extent = derive_and_close(
        set(), attr_to_objs, all_obj_indices, all_attr_indices
    )
    concepts.append((current_intent, current_extent))

    while True:
        next_concept = None
        
        # Parcours des attributs du plus grand indice au plus petit (ordre lectic descendant)
        for m in range(num_attrs - 1, -1, -1):
            if m in current_intent:
                continue  # L'attribut est déjà dans l'intention courante

            # A = B ∩ {0, ..., m-1}
            lower_bound_attrs = set(range(m))
            A = current_intent & lower_bound_attrs

            # Calcul de la fermeture candidate C = (A ∪ {m})''
            cand_intent, cand_extent = derive_and_close(
                A | {m}, attr_to_objs, all_obj_indices, all_attr_indices
            )

            # Condition de NextClosure :
            # 1. m doit appartenir à l'intention candidate (garantit l'ajout de m)
            # 2. La partie inférieure de C doit être identique à celle de B
            #    (garantit l'ordre lectic strict sans saut)
            if m in cand_intent and (cand_intent & lower_bound_attrs) == (current_intent & lower_bound_attrs):
                next_concept = (cand_intent, cand_extent)
                break  # Premier m valide trouvé = successeur lectic immédiat

        if next_concept is None:
            break  # Aucun successeur : fin du treillis (borne supérieure atteinte)
            
        concepts.append(next_concept)
        current_intent, current_extent = next_concept

    return concepts


def build_hasse_diagram(concepts: List[Tuple[Set[int], Set[int]]]) -> List[Tuple[int, int]]:
    """
    Calcule les relations de couverture (Hasse) du treillis.
    Un concept j couvre i si Ext(i) ⊂ Ext(j) et ∄k tel que Ext(i) ⊂ Ext(k) ⊂ Ext(j).
    """
    n = len(concepts)
    edges: List[Tuple[int, int]] = []  # (enfant_id, parent_id)
    
    # Pré-calcul des inclusions strictes pour optimiser
    is_strict_subset = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and concepts[i][1].issubset(concepts[j][1]) and concepts[i][1] != concepts[j][1]:
                is_strict_subset[i][j] = True

    for i in range(n):
        for j in range(n):
            if not is_strict_subset[i][j]:
                continue
                
            # Vérifier s'il existe un intermédiaire k
            is_cover = True
            for k in range(n):
                if is_strict_subset[i][k] and is_strict_subset[k][j]:
                    is_cover = False
                    break
            if is_cover:
                edges.append((i, j))
                
    return edges


def generate_dot(
    concepts: List[Tuple[Set[int], Set[int]]],
    edges: List[Tuple[int, int]],
    obj_names: List[str],
    attr_names: List[str]
) -> str:
    """
    Génère la chaîne DOT conforme au format imposé.
    Applique le styling conditionnel aux nœuds extrémaux et pivot.
    """
    n = len(concepts)
    num_attrs = len(attr_names)
    
    # Identification des concepts extrémaux et pivot
    bottom_idx = 0  # NextClosure commence toujours par l'intention vide
    top_idx = next(i for i, (intent, extent) in enumerate(concepts) if not extent)
    
    # Pivot : premier concept intermédiaire (ni borne inf, ni borne sup)
    pivot_idx = next((i for i in range(n) if i != bottom_idx and i != top_idx), None)

    lines = ["digraph G {", "    rankdir=BT;"]

    for idx, (intent, extent) in enumerate(concepts):
        # Formatage des listes
        attr_list = "\n".join(attr_names[a] for a in sorted(intent)) if intent else ""
        obj_list = "\n".join(obj_names[o] for o in sorted(extent)) if extent else ""
        
        # Construction du label record
        label = f"{{{idx} (I: {len(intent)}, E: {len(extent)})|{attr_list}|{obj_list}}}"
        
        # Application du styling conditionnel
        if idx == bottom_idx or idx == top_idx:
            node_def = f'    {idx} [shape=record,style=filled,fillcolor=lightblue,label="{label}"];'
        elif idx == pivot_idx:
            node_def = f'    {idx} [shape=record,style=filled,fillcolor=orange,label="{label}"];'
        else:
            node_def = f'    {idx} [shape=record,label="{label}"];'
            
        lines.append(node_def)

    for child, parent in edges:
        lines.append(f"    {child} -> {parent}")

    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    """Point d'entrée principal : orchestration, mesure CPU et I/O."""
    if len(sys.argv) != 2:
        print("Usage: python lattice_generator.py <chemin_vers_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]

    # 1. Lecture et validation
    try:
        obj_names, attr_names, context = read_and_validate_csv(csv_path)
    except Exception as e:
        print(f"Erreur de validation CSV : {e}", file=sys.stderr)
        sys.exit(1)

    num_attrs = len(attr_names)
    all_attr_idx = set(range(num_attrs))
    all_obj_idx = set(range(len(obj_names)))
    attr_to_objs = precompute_mappings(context, num_attrs)

    # 2. Calcul du treillis (mesure CPU stricte)
    start_cpu = time.process_time()
    concepts = generate_lattice(num_attrs, attr_to_objs, all_obj_idx, all_attr_idx)
    edges = build_hasse_diagram(concepts)
    end_cpu = time.process_time()

    # 3. Génération et écriture DOT
    dot_content = generate_dot(concepts, edges, obj_names, attr_names)
    output_path = os.path.join(os.path.dirname(os.path.abspath(csv_path)), "output.dot")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dot_content)

    # 4. Affichage du temps CPU
    print(f"Temps CPU : {end_cpu - start_cpu:.4f} secondes")
    print(f"Treillis généré : {len(concepts)} concepts, {len(edges)} arêtes.")
    print(f"Exporté vers : {output_path}")


if __name__ == "__main__":
    main()