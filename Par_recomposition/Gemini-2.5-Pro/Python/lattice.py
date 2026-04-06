import csv
import json
import os
import gc
import time
import threading
from datetime import timedelta
from collections import defaultdict
import pandas as pd
import numpy as np

# --- Configuration ---
PARTITION_DIR = "partition"
PARTITION_SIZE = 10  # Nombre d'attributs par partition. Ajuster selon la RAM.
PROGRESS_INTERVAL_SECONDS = 600  # 10 minutes

class ProgressLogger:
    """Gère l'affichage de la progression dans un thread séparé."""
    def __init__(self, total):
        self.total = total
        self.processed_count = 0
        self.start_time = time.time()
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        """Boucle principale du thread de logging."""
        while not self._stop_event.wait(PROGRESS_INTERVAL_SECONDS):
            self.log_progress()

    def start(self):
        """Démarre le logger."""
        if self.total > 0:
            self.start_time = time.time()
            self.thread.start()

    def stop(self):
        """Arrête le logger et affiche le message final."""
        if self.thread.is_alive():
            self._stop_event.set()
            self.thread.join(timeout=1)
        elapsed_time_str = self.get_elapsed_time()
        print(f"[{elapsed_time_str}] [Avancement: 100%] Calcul des relations de couverture terminé.")

    def increment(self):
        """Incrémente le compteur d'éléments traités."""
        self.processed_count += 1

    def get_elapsed_time(self):
        """Retourne le temps écoulé formaté."""
        elapsed_seconds = time.time() - self.start_time
        return str(timedelta(seconds=int(elapsed_seconds)))

    def log_progress(self):
        """Affiche le message de progression."""
        if self.total == 0: return
        percentage = (self.processed_count / self.total) * 100
        elapsed_time_str = self.get_elapsed_time()
        print(
            f"[{elapsed_time_str}] [Avancement: {percentage:.0f}%] "
            "Calcul des relations de couverture en cours..."
        )

def load_context(csv_path):
    """
    Charge un contexte formel depuis un fichier CSV.
    Retourne les objets, les attributs et la matrice binaire.
    """
    print(f"Chargement du contexte depuis {csv_path}...")
    try:
        df = pd.read_csv(csv_path, sep=';', index_col=0)
        df = df.fillna(0).astype(bool)
        objects = df.index.tolist()
        attributes = df.columns.tolist()
        matrix = df.to_numpy()
        print(f"Contexte chargé : {len(objects)} objets, {len(attributes)} attributs.")
        return objects, attributes, matrix
    except FileNotFoundError:
        print(f"Erreur : Le fichier {csv_path} n'a pas été trouvé.")
        exit(1)
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier CSV : {e}")
        exit(1)

def closure(matrix, attr_indices):
    """
    Calcule la fermeture de Galois (A'', A').
    A est un ensemble d'indices d'attributs.
    """
    if not attr_indices:
        # Fermeture de l'ensemble vide
        obj_indices = np.ones(matrix.shape[0], dtype=bool)
    else:
        # A' : objets qui ont tous les attributs de A
        obj_indices = matrix[:, attr_indices].all(axis=1)

    # A'' : attributs communs à tous les objets de A'
    if not obj_indices.any():
        # Si aucun objet, l'intent est tous les attributs
        new_attr_indices = np.ones(matrix.shape[1], dtype=bool)
    else:
        new_attr_indices = matrix[obj_indices, :].all(axis=0)

    return np.where(new_attr_indices)[0], np.where(obj_indices)[0]

def next_closure_partition(context, partition_attrs_indices):
    """
    Algorithme NextClosure pour une partition d'attributs.
    Génère tous les concepts dont l'intent est inclus dans la partition.
    """
    objects, attributes, matrix = context
    num_attributes = len(attributes)
    
    concepts = []
    
    # Démarrer avec la fermeture de l'ensemble vide
    intent_indices, extent_indices = closure(matrix, [])
    concepts.append({
        "intent": [attributes[i] for i in intent_indices],
        "extent": [objects[i] for i in extent_indices]
    })
    
    processed_intents = {tuple(sorted(intent_indices))}

    # Utiliser une pile pour gérer les intents à explorer
    # On ne démarre qu'avec les attributs de la partition
    stack = [(list(intent_indices), -1)]

    while stack:
        current_intent_indices, start_attr_idx = stack.pop()
        
        for i in range(start_attr_idx + 1, num_attributes):
            # On ne génère de nouveaux candidats qu'à partir des attributs de la partition
            if i not in partition_attrs_indices:
                continue

            if i in current_intent_indices:
                continue

            new_intent_candidate_indices = sorted(list(set(current_intent_indices) | {i}))
            
            closed_intent_indices, closed_extent_indices = closure(matrix, new_intent_candidate_indices)
            
            # Vérifier si le concept est nouveau
            intent_key = tuple(sorted(closed_intent_indices))
            if intent_key not in processed_intents:
                concepts.append({
                    "intent": [attributes[j] for j in closed_intent_indices],
                    "extent": [objects[j] for j in closed_extent_indices]
                })
                processed_intents.add(intent_key)
                stack.append((list(closed_intent_indices), i))

    return concepts


def save_partition(partition_index, concepts):
    """Sauvegarde une partition de concepts sur le disque."""
    part_dir = os.path.join(PARTITION_DIR, f"part_{partition_index}")
    os.makedirs(part_dir, exist_ok=True)
    
    # Découper en chunks si la partition est trop grande
    chunk_size = 10000
    for i in range(0, len(concepts), chunk_size):
        chunk = concepts[i:i+chunk_size]
        file_path = os.path.join(part_dir, f"concepts_chunk_{i//chunk_size}.json")
        with open(file_path, 'w') as f:
            json.dump(chunk, f, indent=2)

def load_partitions():
    """Charge et fusionne toutes les partitions de concepts en dédupliquant."""
    print("Chargement et fusion des partitions...")
    unique_concepts = {}
    if not os.path.exists(PARTITION_DIR):
        print("Avertissement : Le dossier des partitions n'existe pas.")
        return []

    partition_folders = sorted(os.listdir(PARTITION_DIR))
    for part_folder in partition_folders:
        part_dir_path = os.path.join(PARTITION_DIR, part_folder)
        if not os.path.isdir(part_dir_path):
            continue
        
        for chunk_file in sorted(os.listdir(part_dir_path)):
            if chunk_file.endswith(".json"):
                file_path = os.path.join(part_dir_path, chunk_file)
                with open(file_path, 'r') as f:
                    concepts = json.load(f)
                    for concept in concepts:
                        # Clé de déduplication : tuple trié des attributs de l'intent
                        key = tuple(sorted(concept['intent']))
                        if key not in unique_concepts:
                            unique_concepts[key] = concept
    
    print(f"Total de {len(unique_concepts)} concepts uniques trouvés.")
    return list(unique_concepts.values())

def compute_edges(concepts, progress_logger):
    """Calcule les arêtes de couverture du treillis de manière optimisée."""
    print("Calcul des relations de couverture...")
    if not concepts:
        return [], {}

    # Mapper les intents (repr. string) aux IDs pour un accès rapide
    intent_map = {tuple(sorted(c['intent'])): i for i, c in enumerate(concepts)}
    
    # Indexer les concepts par la taille de leur intent
    concepts_by_size = defaultdict(list)
    for i, c in enumerate(concepts):
        concepts_by_size[len(c['intent'])].append(i)

    edges = []
    # Structure pour stocker les parents/enfants de chaque concept
    # parents[concept_id] = {parent_id_1, parent_id_2, ...}
    parents_map = defaultdict(set)
    children_map = defaultdict(set)

    # Trier les concepts par taille d'intent (décroissant) pour la recherche des parents
    sorted_concepts_indices = sorted(range(len(concepts)), key=lambda i: len(concepts[i]['intent']), reverse=True)

    progress_logger.start()

    for i in sorted_concepts_indices:
        concept = concepts[i]
        concept_intent_set = set(concept['intent'])
        
        # Les parents potentiels ont une taille d'intent de +1
        potential_parents_size = len(concept['intent']) + 1
        
        # Chercher les parents parmi les concepts de la bonne taille
        for parent_idx in concepts_by_size.get(potential_parents_size, []):
            parent_concept = concepts[parent_idx]
            if concept_intent_set.issubset(set(parent_concept['intent'])):
                # C'est un parent, est-ce un parent de couverture ?
                # On vérifie qu'aucun enfant du parent n'est un parent de notre concept
                is_cover = True
                # Les enfants du parent ont déjà été calculés car ils sont plus petits
                for child_of_parent_id in children_map.get(parent_idx, []):
                    child_of_parent_intent = set(concepts[child_of_parent_id]['intent'])
                    if concept_intent_set.issubset(child_of_parent_intent):
                        is_cover = False
                        break
                
                if is_cover:
                    edges.append((i, parent_idx))
                    parents_map[i].add(parent_idx)
                    children_map[parent_idx].add(i)
        
        progress_logger.increment()

    progress_logger.stop()
    
    return edges, {"parents": parents_map, "children": children_map}


def write_dot(output_path, concepts, edges, relations):
    """Génère le fichier DOT final."""
    print(f"Génération du fichier DOT : {output_path}...")
    
    # Trier les concepts pour une sortie déterministe (par taille d'intent, puis par nom)
    concept_ids = sorted(range(len(concepts)), key=lambda i: (len(concepts[i]['intent']), sorted(concepts[i]['intent'])))
    id_map = {old_id: new_id for new_id, old_id in enumerate(concept_ids)}

    with open(output_path, 'w') as f:
        f.write("digraph G {\n")
        f.write("rankdir=BT;\n\n")

        # Écrire les noeuds
        for new_id, old_id in enumerate(concept_ids):
            concept = concepts[old_id]
            
            # Calculer les objets propres (extent propre)
            own_extent = set(concept['extent'])
            for child_id in relations['children'].get(old_id, []):
                own_extent -= set(concepts[child_id]['extent'])
            
            # Calculer les attributs propres (intent propre)
            own_intent = set(concept['intent'])
            for parent_id in relations['parents'].get(old_id, []):
                own_intent -= set(concepts[parent_id]['intent'])

            # Déterminer la couleur
            num_own_objects = len(own_extent)
            fillcolor = ""
            if num_own_objects == 0:
                fillcolor = ",fillcolor=lightblue"
            elif num_own_objects > 1:
                fillcolor = ",fillcolor=orange"

            # Formater les labels
            intent_label = ", ".join(sorted(list(own_intent))).replace('"', '\\"')
            extent_label = ", ".join(sorted(list(own_extent))).replace('"', '\\"')
            
            label = (
                f'"{new_id} (I: {len(concept["intent"])}, E: {len(concept["extent"])})|'
                f'{{{intent_label}}} | {{{extent_label}}}"'
            )
            
            f.write(f'{new_id} [shape=record,style=filled{fillcolor},label={label}];\n')

        f.write("\n")

        # Écrire les arêtes
        for child_old_id, parent_old_id in edges:
            f.write(f"{id_map[child_old_id]} -> {id_map[parent_old_id]};\n")

        f.write("}\n")
    print("Fichier DOT généré avec succès.")


def main(csv_path):
    """Pipeline principal."""
    start_total_time = time.time()
    
    input_dir = os.path.dirname(csv_path)
    base_name = os.path.splitext(os.path.basename(csv_path))[0]
    output_dir = os.path.join(input_dir, "Lattice")
    os.makedirs(output_dir, exist_ok=True)
    dot_output_path = os.path.join(output_dir, f"{base_name}_LLM.dot")

    # --- Étape 1-7: Calcul des concepts par partitions ---
    context = load_context(csv_path)
    objects, attributes, matrix = context
    
    if os.path.exists(PARTITION_DIR):
        import shutil
        shutil.rmtree(PARTITION_DIR)
    
    attribute_indices = list(range(len(attributes)))
    num_partitions = (len(attributes) + PARTITION_SIZE - 1) // PARTITION_SIZE

    print(f"Décomposition en {num_partitions} partitions de taille max {PARTITION_SIZE}...")
    for i in range(num_partitions):
        start = i * PARTITION_SIZE
        end = start + PARTITION_SIZE
        partition_attrs_indices = attribute_indices[start:end]
        
        print(f"Calcul de la partition {i+1}/{num_partitions}...")
        partition_concepts = next_closure_partition(context, partition_attrs_indices)
        
        print(f"Sauvegarde de {len(partition_concepts)} concepts pour la partition {i+1}...")
        save_partition(i, partition_concepts)
        
        # Libération explicite de la mémoire
        del partition_concepts
        gc.collect()

    # Libérer la mémoire du contexte initial avant la fusion
    del context, objects, attributes, matrix
    gc.collect()

    # --- Étape 8: Rechargement et fusion ---
    all_concepts = load_partitions()
    
    # --- Étape 9: Calcul des relations ---
    progress_logger = ProgressLogger(total=len(all_concepts))
    edges, relations = compute_edges(all_concepts, progress_logger)
    
    # --- Étape 10: Génération du DOT ---
    write_dot(dot_output_path, all_concepts, edges, relations)
    
    end_total_time = time.time()
    print(f"\nTerminé en {timedelta(seconds=int(end_total_time - start_total_time))}.")
    print(f"Sortie disponible dans : {dot_output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python3 lattice.py <Nom du fichier>.csv")
        sys.exit(1)
    main(sys.argv[1])