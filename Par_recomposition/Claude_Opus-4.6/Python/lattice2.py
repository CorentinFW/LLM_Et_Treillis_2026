#!/usr/bin/env python3
"""
lattice2.py — Formal Concept Analysis: Memory-efficient lattice computation
              via partitioned NextClosure with disk-based intermediate storage.

Computes all formal concepts and the covering relation (Hasse diagram) of the
concept lattice from a binary formal context stored in a CSV file.

===========================================================================
Hypothèses et choix de conception
===========================================================================

1. Le CSV utilise le séparateur « ; ».  Les cellules valent 0 ou 1.
   La première ligne contient les noms d'attributs (première cellule vide).
   La première colonne contient les noms d'objets.

2. Les objets et attributs sont représentés par des bitmasks (entiers Python
   à précision arbitraire).  Ceci permet des intersections en O(1) au niveau
   machine (modulo la taille du mot) et une empreinte mémoire compacte.

3. Le contexte formel (matrices obj_attrs et attr_objs) tient en mémoire
   pendant toute l'exécution — seule la liste croissante de concepts est
   vidangée sur disque par lots (partitions).

4. L'algorithme NextClosure (Ganter, 1984) est utilisé pour l'énumération
   en ordre lectique.  Il assure une production déterministe, sans doublons,
   de tous les concepts formels.

5. La décomposition est effectuée sur le FLUX DE SORTIE de NextClosure :
   tous les batch_size concepts consécutifs forment une partition écrite sur
   disque.  Chaque partition peut elle-même être découpée en fichiers JSON
   (chunks) de taille CHUNK_SIZE pour un rechargement plus fin.

6. La taille des batchs est calculée dynamiquement en fonction de la RAM
   disponible (/proc/meminfo sous Linux, avec fallback conservateur).

7. Le calcul des arêtes de couverture est optimisé par un index par niveau
   (cardinalité de l'intent), ce qui évite les comparaisons entre concepts
   de même niveau ou de niveau supérieur.

8. La sortie DOT est déterministe : les nœuds sont numérotés dans l'ordre
   trié par (|intent|, valeur du masque intent), et les arêtes sont triées.

===========================================================================
Complexités
===========================================================================

Soit |G| = nombre d'objets, |M| = nombre d'attributs, |L| = nombre de
concepts, w = taille du mot machine (64).

- Chargement du contexte :          O(|G| × |M|)
- Fermeture X'' :                   O(|G| + |M|)  par appel  (O((|G|+|M|)/w))
- Énumération NextClosure complète: O(|L| × |M| × (|G|+|M|) / w)
- Calcul des arêtes :               O(|L|² × |M| / w)  (pire cas)
                                     amélioré par l'index par niveau
- Génération DOT :                  O(|L| + |E|)  où |E| = nombre d'arêtes

===========================================================================
Usage
===========================================================================

    python lattice2.py <context.csv>

Sortie :
    <dirname>/Lattice/<basename>_LLM_2.dot

Exemple :
    python lattice2.py Animals11/Animals11.csv
    → Animals11/Lattice/Animals11_LLM_2.dot
"""

import csv
import os
import json
import gc
import sys
import shutil


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Nombre par défaut de concepts par partition (ajusté dynamiquement).
BATCH_SIZE_DEFAULT = 500

# Nombre maximal de concepts par fichier JSON chunk dans une partition.
CHUNK_SIZE = 200

# RAM minimale à conserver libre (Mo).
MEMORY_RESERVE_MB = 100

# Nom du répertoire de travail pour les partitions.
PARTITION_DIR_NAME = "partition"

# Intervalle d'affichage de la progression pendant l'énumération.
PROGRESS_INTERVAL = 1000


# ===================================================================
# Utilitaires mémoire
# ===================================================================

def get_available_memory_mb():
    """
    Retourne la RAM disponible estimée en mégaoctets.

    Sous Linux, lit /proc/meminfo (ligne MemAvailable).
    Retourne un défaut conservateur (1024 Mo) en cas d'échec.
    """
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    parts = line.split()
                    return int(parts[1]) / 1024.0  # kB -> MB
    except (IOError, ValueError, IndexError):
        pass
    return 1024.0


def compute_adaptive_batch_size(n_attrs, n_objs):
    """
    Calcule une taille de batch adaptée à la RAM disponible et aux
    dimensions du contexte.

    Heuristique :
    - Chaque concept en mémoire est un tuple de deux entiers Python
      (intent_mask, extent_mask).
    - Coût estimé : ~300 octets par concept (incluant l'overhead CPython
      pour les ints, le tuple, et les structures de liste).
    - On utilise au plus 40 % de la RAM disponible pour le buffer.
    - Le résultat est borné entre 100 et 50 000.
    """
    available_mb = get_available_memory_mb()
    usable_mb = max((available_mb - MEMORY_RESERVE_MB) * 0.4, 20.0)
    bytes_per_concept = max(300, (n_attrs + n_objs) // 2)
    batch = int((usable_mb * 1024 * 1024) / bytes_per_concept)
    return max(100, min(batch, 50000))


# ===================================================================
# Utilitaires bitmask
# ===================================================================

def popcount(mask):
    """Retourne le nombre de bits à 1 dans mask (poids de Hamming)."""
    return bin(mask).count('1')


def bitmask_to_names(mask, names):
    """
    Convertit un bitmask en liste de noms, dans l'ordre original.

    Le bit i correspond à names[i].
    """
    result = []
    for i, name in enumerate(names):
        if mask & (1 << i):
            result.append(name)
    return result


def names_to_bitmask(name_list, name_to_idx):
    """
    Convertit une liste de noms en bitmask via un dictionnaire nom→index.
    """
    mask = 0
    for name in name_list:
        mask |= (1 << name_to_idx[name])
    return mask


# ===================================================================
# Étape 1 — Chargement du contexte formel
# ===================================================================
#
# Le CSV est parsé sans hypothèse sur le nombre de lignes ou de colonnes.
#
# Structures de données choisies :
#   - objects    : list[str]  — noms des objets, ordre du CSV préservé.
#   - attributes : list[str]  — noms des attributs, ordre du CSV préservé.
#   - obj_attrs  : list[int]  — obj_attrs[g] = bitmask des attributs de l'objet g.
#   - attr_objs  : list[int]  — attr_objs[m] = bitmask des objets possédant m.
#
# La représentation par bitmask est compacte (un entier Python par ligne/colonne)
# et permet des intersections en temps constant grâce au AND bit à bit.
#
# Complexité : O(|G| × |M|) en temps et en espace.
# ===================================================================

def load_context(csv_path):
    """
    Parse un contexte formel binaire depuis un fichier CSV délimité par « ; ».

    Parameters
    ----------
    csv_path : str — chemin vers le fichier CSV.

    Returns
    -------
    objects    : list[str]
    attributes : list[str]
    obj_attrs  : list[int]  — bitmask-lignes
    attr_objs  : list[int]  — bitmask-colonnes
    n_objs     : int
    n_attrs    : int
    """
    objects = []
    attributes = []
    obj_attrs = []

    with open(csv_path, 'r', newline='', encoding='utf-8') as fh:
        reader = csv.reader(fh, delimiter=';')
        header = next(reader)
        # Première cellule vide ou label — on l'ignore.
        attributes = [a.strip() for a in header[1:]]
        n_attrs = len(attributes)

        for row in reader:
            if not row or all(c.strip() == '' for c in row):
                continue  # Ligne vide
            obj_name = row[0].strip()
            objects.append(obj_name)
            mask = 0
            for j in range(n_attrs):
                val = row[1 + j].strip() if (1 + j) < len(row) else '0'
                if val == '1':
                    mask |= (1 << j)
            obj_attrs.append(mask)

    n_objs = len(objects)

    # Pré-calcul des bitmasks colonnes : attr_objs[m] = ensemble des objets
    # possédant l'attribut m.
    attr_objs = [0] * n_attrs
    for g in range(n_objs):
        tmp = obj_attrs[g]
        m = 0
        while tmp:
            if tmp & 1:
                attr_objs[m] |= (1 << g)
            tmp >>= 1
            m += 1

    return objects, attributes, obj_attrs, attr_objs, n_objs, n_attrs


# ===================================================================
# Étape 2 — Opérateur de fermeture
# ===================================================================
#
# L'opérateur de fermeture X'' se décompose en deux opérations :
#
# 1. X' (prime_attrs) : pour un ensemble d'attributs X, calculer l'ensemble
#    des objets possédant TOUS les attributs de X.
#    → Intersection (AND) des bitmasks-colonnes pour chaque attribut dans X.
#    → Si X est vide, tous les objets satisfont (vérité vacuouse).
#
# 2. Y' (prime_objs) : pour un ensemble d'objets Y, calculer l'ensemble
#    des attributs partagés par TOUS les objets de Y.
#    → Intersection (AND) des bitmasks-lignes pour chaque objet dans Y.
#    → Si Y est vide, tous les attributs sont partagés.
#
# Complexité de X' :  O(|X|) opérations AND  ≤  O(|M|)
# Complexité de Y' :  O(|Y|) opérations AND  ≤  O(|G|)
# Complexité de X'' = (X')' :  O(|G| + |M|)
#
# Chaque opération AND sur des entiers Python de taille k bits coûte O(k/w)
# dans le modèle RAM classique (w = taille du mot machine).
# ===================================================================

def prime_attrs(attr_set, attr_objs, all_objs):
    """
    X' — ensemble des objets possédant TOUS les attributs de X.

    Complexity: O(|M|) bitwise AND operations.
    """
    if attr_set == 0:
        return all_objs
    extent = all_objs
    m = 0
    tmp = attr_set
    while tmp:
        if tmp & 1:
            extent &= attr_objs[m]
        tmp >>= 1
        m += 1
    return extent


def prime_objs(obj_set, obj_attrs, all_attrs):
    """
    Y' — ensemble des attributs partagés par TOUS les objets de Y.

    Complexity: O(|G|) bitwise AND operations.
    """
    if obj_set == 0:
        return all_attrs
    intent = all_attrs
    g = 0
    tmp = obj_set
    while tmp:
        if tmp & 1:
            intent &= obj_attrs[g]
        tmp >>= 1
        g += 1
    return intent


def closure(attr_set, attr_objs, obj_attrs, all_objs, all_attrs):
    """
    Fermeture double-prime X'' et extent intermédiaire X'.

    Returns (intent, extent) comme paire de bitmasks.

    Complexity: O(|G| + |M|).
    """
    extent = prime_attrs(attr_set, attr_objs, all_objs)
    intent = prime_objs(extent, obj_attrs, all_attrs)
    return intent, extent


# ===================================================================
# Étape 3 — Énumération NextClosure (Ganter, 1984)
# ===================================================================
#
# Ordre lectique :
#   L'ordre lectique est un ordre total sur les sous-ensembles de M (attributs).
#   Il est défini par l'indexation des attributs : l'attribut d'indice 0 est
#   le plus « significatif ».  Formellement, A <_i B ssi l'attribut i-1 est
#   dans B\A et A ∩ {0,..,i-2} = B ∩ {0,..,i-2}.
#
# Génération des candidats :
#   Pour chaque position i de |M|-1 à 0, on tente d'ajouter l'attribut i
#   au préfixe inférieur du concept courant :
#     candidate = (current_intent ∩ {0,..,i-1}) ∪ {i}
#
# Usage de la fermeture :
#   On calcule candidate'' = (D_intent, D_extent).  Si le préfixe inférieur
#   de D_intent coïncide avec celui de current_intent, alors D est le
#   prochain ensemble fermé.
#
# Condition d'arrêt :
#   Quand aucune position i ne produit de candidat valide, l'énumération est
#   terminée (nous avons atteint M ou le dernier ensemble fermé).
#
# Exhaustivité :
#   L'ordre lectique parcourt toutes les parties de M.  La fermeture
#   saute les parties non fermées.  Le test de canonicité (préfixe)
#   garantit qu'on ne produit chaque fermé qu'une seule fois.  Donc
#   tous les concepts sont énumérés, exactement une fois.
#
# Complexité théorique :
#   O(|M|) appels de fermeture par avancée, chaque fermeture en O(|G|+|M|).
#   Total pour l'énumération complète : O(|L| × |M| × (|G|+|M|) / w).
#
# Limites pratiques :
#   |L| peut être exponentiel en |M| dans le pire cas (|L| ≤ 2^min(|G|,|M|)).
#   Pour des contextes denses avec |M| ≥ 30–40, le nombre de concepts peut
#   dépasser la mémoire ou le temps raisonnable.
# ===================================================================

def next_closure(current_intent, n_attrs, attr_objs, obj_attrs,
                 all_objs, all_attrs):
    """
    Calcule le prochain ensemble fermé après current_intent en ordre lectique.

    Returns (intent, extent) ou None si l'énumération est terminée.
    """
    for i in range(n_attrs - 1, -1, -1):
        bit_i = 1 << i
        if not (current_intent & bit_i):
            # Candidat : préfixe strict < i du courant, plus l'attribut i
            prefix_mask = (1 << i) - 1  # bits 0..i-1
            candidate = (current_intent & prefix_mask) | bit_i
            d_intent, d_extent = closure(candidate, attr_objs, obj_attrs,
                                         all_objs, all_attrs)
            # Test de canonicité : le préfixe doit être inchangé
            if (d_intent & prefix_mask) == (current_intent & prefix_mask):
                return d_intent, d_extent
    return None


# ===================================================================
# Étape 5 — Stockage intermédiaire sur disque
# ===================================================================
#
# Chaque partition est un répertoire contenant un ou plusieurs fichiers
# JSON (chunks).
#
# Structure :
#   partition/
#     part0/
#       chunk0.json
#       chunk1.json
#     part1/
#       chunk0.json
#     ...
#
# Format JSON de chaque chunk :
#   [
#     {"intent": ["attr1", "attr2"], "extent": ["obj1"]},
#     ...
#   ]
#
# Le découpage en chunks de taille CHUNK_SIZE (défaut 200) permet un
# rechargement ultérieur plus granulaire : on peut lire un chunk à la
# fois sans charger toute la partition.
#
# Stratégie d'écriture :
#   Écriture par lots (json.dump) plutôt qu'en flux, car chaque chunk
#   est de taille bornée par CHUNK_SIZE.  Le coût mémoire de la
#   sérialisation est donc contrôlé.
#
# Complexité : O(batch_size × (|G| + |M|)) pour la conversion bitmask→noms.
# ===================================================================

def save_partition(concepts, partition_path, attributes, objects,
                   n_attrs, n_objs, chunk_size=CHUNK_SIZE):
    """
    Sérialise un lot de concepts dans des fichiers JSON découpés en chunks.

    Parameters
    ----------
    concepts       : list[(int, int)] — paires (intent_mask, extent_mask)
    partition_path : str              — répertoire de la partition
    attributes     : list[str]        — noms des attributs
    objects        : list[str]        — noms des objets
    n_attrs        : int
    n_objs         : int
    chunk_size     : int              — max concepts par fichier JSON
    """
    os.makedirs(partition_path, exist_ok=True)

    total = len(concepts)
    chunk_idx = 0

    for start in range(0, total, chunk_size):
        end = min(start + chunk_size, total)
        records = []
        for intent_mask, extent_mask in concepts[start:end]:
            records.append({
                "intent": bitmask_to_names(intent_mask, attributes),
                "extent": bitmask_to_names(extent_mask, objects),
            })
        filepath = os.path.join(partition_path, f"chunk{chunk_idx}.json")
        with open(filepath, 'w', encoding='utf-8') as fh:
            json.dump(records, fh, ensure_ascii=False)
        del records
        chunk_idx += 1


# ===================================================================
# Étape 4 — Décomposition en sous-parties
# ===================================================================
#
# Définition d'une sous-partie :
#   Une sous-partie (partition) est un segment contigu de batch_size concepts
#   produits par NextClosure en ordre lectique.  Puisque l'ordre lectique est
#   total et déterministe, chaque concept apparaît dans exactement une
#   partition.
#
# Choix de la taille :
#   La taille est calculée dynamiquement par compute_adaptive_batch_size()
#   en fonction de la RAM disponible.  Plus la RAM est abondante, plus le
#   batch est grand (moins d'I/O disque).
#
# Absence de doublons :
#   L'ordre lectique visite chaque ensemble fermé exactement une fois.
#   Le partitionnement du flux de sortie ne peut donc produire de doublons.
#
# Couverture complète :
#   NextClosure est prouvé exhaustif.  Tous les concepts sont produits donc
#   tous sont couverts par les partitions.
#
# Pas de décomposition par sous-espaces d'attributs :
#   Une décomposition par blocs d'attributs (p. ex. attributs 0-5, 6-10, ...)
#   ne garantirait pas la couverture complète sans mécanisme complémentaire
#   de fermeture croisée.  Le partitionnement du flux de sortie est plus
#   simple, correct par construction, et tout aussi efficace en contrôle
#   mémoire.
# ===================================================================
#
# Étape 6 — Libération mémoire
# ===================================================================
#
# Après chaque partition :
#   - del buffer       — libère la liste de tuples (intent, extent)
#   - gc.collect()     — force la collecte des cycles de références
#
# Variables conservées en permanence :
#   - attr_objs, obj_attrs, all_objs, all_attrs  (matrice du contexte,
#     nécessaire pour la fermeture)
#   - attributes, objects  (listes de noms, nécessaires pour la sérialisation)
#   - current_intent       (un seul entier, l'intent courant de NextClosure)
#   - part_idx, total      (compteurs)
#
# Variables libérées entre les partitions :
#   - buffer / concepts    (le lot de tuples de concepts)
#   - records              (structure JSON intermédiaire dans save_partition)
# ===================================================================
#
# Étape 7 — Boucle principale de calcul
# ===================================================================
#
# Déroulement :
# 1. Calculer le premier concept (fermeture de l'ensemble vide).
# 2. Boucle :
#    a. Appeler next_closure() pour obtenir le concept suivant.
#    b. L'ajouter au buffer.
#    c. Si le buffer atteint batch_size :
#       i.   Sauvegarder la partition sur disque (save_partition).
#       ii.  Supprimer le buffer (del buffer ; gc.collect()).
#       iii. Créer un nouveau buffer vide.
#       iv.  Incrémenter l'index de partition.
#    d. Quand next_closure() retourne None, vidanger le buffer restant.
# 3. Retourner le total de concepts énumérés.
#
# Cette boucle permet de traiter de grands contextes car la mémoire est
# bornée à O(batch_size) concepts + O(|G| × |M|) pour le contexte.
# ===================================================================

def next_closure_partition(n_attrs, attr_objs, obj_attrs, all_objs, all_attrs,
                           attributes, objects, partition_dir, batch_size):
    """
    Énumère TOUS les concepts formels via NextClosure et les écrit sur disque
    par partitions de taille batch_size.

    Returns : int — nombre total de concepts énumérés.
    """
    n_objs = len(objects)

    # Nettoyer et créer le répertoire de partitions
    if os.path.exists(partition_dir):
        shutil.rmtree(partition_dir)
    os.makedirs(partition_dir)

    # --- Premier concept : fermeture de l'ensemble vide ---
    first_intent, first_extent = closure(0, attr_objs, obj_attrs,
                                         all_objs, all_attrs)
    buffer = [(first_intent, first_extent)]
    current_intent = first_intent
    part_idx = 0
    total = 1

    while True:
        result = next_closure(current_intent, n_attrs, attr_objs, obj_attrs,
                              all_objs, all_attrs)
        if result is None:
            break

        intent, extent = result
        buffer.append((intent, extent))
        current_intent = intent
        total += 1

        # Affichage de la progression
        if total % PROGRESS_INTERVAL == 0:
            print(f"    ... {total} concepts énumérés", flush=True)

        # --- Vidanger le buffer dans une partition ---
        if len(buffer) >= batch_size:
            part_path = os.path.join(partition_dir, f"part{part_idx}")
            save_partition(buffer, part_path, attributes, objects,
                           n_attrs, n_objs, CHUNK_SIZE)
            part_idx += 1
            # Libération mémoire
            del buffer
            gc.collect()
            buffer = []

    # Vidanger le reste
    if buffer:
        part_path = os.path.join(partition_dir, f"part{part_idx}")
        save_partition(buffer, part_path, attributes, objects,
                       n_attrs, n_objs, CHUNK_SIZE)
        del buffer
        gc.collect()

    return total


# ===================================================================
# Étape 8 — Rechargement et fusion contrôlée des partitions
# ===================================================================
#
# Stratégie de rechargement :
# - On parcourt les répertoires de partitions (part0, part1, ...) dans l'ordre.
# - Dans chaque partition, on parcourt les fichiers chunk (chunk0.json, ...).
# - Avant chaque chargement, on vérifie la RAM disponible ; si elle est
#   insuffisante, on déclenche gc.collect().
# - Les enregistrements JSON sont convertis en tuples (intent_mask, extent_mask).
# - Un ensemble vu (seen) assure la déduplication (filet de sécurité : en théorie
#   NextClosure ne produit pas de doublons, mais cela protège contre les runs
#   interrompus ou partiels).
#
# Chargement multi-partitions :
# - Si la RAM est suffisante (cas courant pour les contextes petits/moyens),
#   toutes les partitions sont chargées en un seul passage.
# - Si la RAM est serrée, les données JSON de chaque chunk sont libérées
#   immédiatement après conversion en bitmasks.
#
# Fusion :
# - Les concepts sont accumulés dans une liste unique.
# - Le seen-set permet de supprimer les doublons en O(1) par concept.
# - La liste est triée par (|intent|, valeur_masque_intent) pour garantir
#   un numérotage de nœuds déterministe et reproductible dans le DOT.
#
# Production d'une vue globale :
# - Pour les contextes de taille modérée (< 100k concepts), tous les concepts
#   tiennent en mémoire après fusion.
# - Pour des contextes très grands, il faudrait un second passage disque pour
#   le calcul des arêtes — ce cas est documenté mais non implémenté ici car
#   il impliquerait un treillis de plusieurs millions de nœuds, pour lequel
#   même le fichier DOT serait inexploitable.
# ===================================================================

def load_partitions(partition_dir, attributes, objects):
    """
    Recharge toutes les partitions, fusionne, déduplique, et trie les concepts.

    Returns : list[(int, int)] — concepts (intent_mask, extent_mask), triés.
    """
    attr_idx = {a: i for i, a in enumerate(attributes)}
    obj_idx = {o: i for i, o in enumerate(objects)}

    seen = set()
    concepts = []

    # Découvrir les répertoires de partitions dans l'ordre numérique
    part_entries = []
    for d in os.listdir(partition_dir):
        dpath = os.path.join(partition_dir, d)
        if os.path.isdir(dpath) and d.startswith("part"):
            try:
                idx = int(d.replace("part", ""))
                part_entries.append((idx, d))
            except ValueError:
                continue
    part_entries.sort()

    for _, pdir_name in part_entries:
        ppath = os.path.join(partition_dir, pdir_name)

        # Découvrir les fichiers chunk dans l'ordre
        chunk_entries = []
        for f in os.listdir(ppath):
            if f.startswith("chunk") and f.endswith('.json'):
                try:
                    cidx = int(f.replace("chunk", "").replace(".json", ""))
                    chunk_entries.append((cidx, f))
                except ValueError:
                    continue
        chunk_entries.sort()

        for _, cfile in chunk_entries:
            filepath = os.path.join(ppath, cfile)

            # Vérification mémoire avant chargement
            if get_available_memory_mb() < MEMORY_RESERVE_MB:
                gc.collect()

            with open(filepath, 'r', encoding='utf-8') as fh:
                raw_data = json.load(fh)

            for rec in raw_data:
                i_mask = names_to_bitmask(rec["intent"], attr_idx)
                e_mask = names_to_bitmask(rec["extent"], obj_idx)
                key = (i_mask, e_mask)
                if key not in seen:
                    seen.add(key)
                    concepts.append(key)

            # Libération des données JSON brutes
            del raw_data
            gc.collect()

    # Libérer le seen-set
    del seen
    gc.collect()

    # Tri déterministe : (cardinalité de l'intent, valeur du masque intent)
    concepts.sort(key=lambda c: (popcount(c[0]), c[0]))
    return concepts


# ===================================================================
# Étape 9 — Calcul optimisé des relations de couverture
# ===================================================================
#
# Définition de la relation de couverture :
#   Le concept c est couvert par le concept d  (c ≺ d, c est EN DESSOUS de d)
#   si et seulement si :
#     - intent(d) ⊂ intent(c)         (d a moins d'attributs — d est AU-DESSUS)
#     - Il n'existe pas de concept e avec intent(d) ⊂ intent(e) ⊂ intent(c)
#
# Dans le diagramme de Hasse (rankdir=BT), les arêtes vont du concept
# inférieur c (plus d'attributs) vers sa couverture supérieure d (moins
# d'attributs) : c → d.
#
# Optimisation par index de niveaux :
# -----------------------------------
# 1. On pré-calcule le « niveau » de chaque concept (= |intent|, sa cardinalité).
# 2. On construit un index par niveau : level_index[k] = liste des indices des
#    concepts ayant |intent| = k.
# 3. Pour le concept c au niveau k, on cherche ses couvertures parmi les niveaux
#    0..k-1 seulement (concepts avec strictement moins d'attributs).
# 4. On traite les niveaux candidats de k-1 vers 0 (couvertures les plus proches
#    en premier).
# 5. On accepte les candidats de façon gloutonne ; un candidat d est DOMINÉ par
#    un parent déjà accepté p si intent(d) ⊂ intent(p) — ce qui signifie que p
#    est entre d et c, donc d n'est pas une couverture directe.
#
# Cette stratégie évite de comparer des concepts au même niveau ou à un niveau
# supérieur, et l'acceptation gloutonne élague les candidats dominés rapidement.
#
# Structure auxiliaire minimale en mémoire :
#   - level_index : un tableau de listes, total O(|L|) en espace.
#   - intent_cards : un tableau de |L| entiers.
#   - accepted_parents : liste temporaire par concept, typiquement de petite taille
#     (bornée par la largeur du treillis aux niveaux adjacents).
#
# Compatibilité avec des concepts répartis dans plusieurs fichiers :
#   Après la fusion (étape 8), tous les concepts sont en mémoire sous forme
#   compacte (deux entiers par concept).  Pour des treillis dépassant la mémoire,
#   on pourrait charger les concepts par blocs de niveaux adjacents et calculer
#   les arêtes entre ces blocs — mais cela nécessiterait un treillis de
#   plusieurs millions de nœuds, pour lequel le DOT serait de toute façon
#   inexploitable.
#
# Complexité :
#   Pire cas : O(|L|² × |M| / w)  (quand le treillis est plat).
#   Cas favorable (treillis profond) : O(|L| × W × |M| / w) où W est la
#   largeur maximale du treillis par niveau.
# ===================================================================

def compute_edges(concepts):
    """
    Calcule la relation de couverture (Hasse) du treillis des concepts.

    Returns : list[(int, int)] — arêtes (child_idx, parent_idx).
    """
    n = len(concepts)
    if n == 0:
        return []

    # Pré-calcul des cardinalités d'intent
    intent_cards = [popcount(concepts[i][0]) for i in range(n)]
    max_card = max(intent_cards)

    # Index par niveau : level_index[k] = indices des concepts avec |intent| = k
    level_index = [[] for _ in range(max_card + 1)]
    for i in range(n):
        level_index[intent_cards[i]].append(i)

    edges = []

    for ci in range(n):
        c_intent = concepts[ci][0]
        c_card = intent_cards[ci]

        if c_card == 0:
            # Concept top (intent minimal) — aucun parent
            continue

        # Chercher les couvertures supérieures :
        # concepts dont l'intent est un sous-ensemble strict de c_intent.
        accepted_parents = []  # intents des parents acceptés

        # Parcours des niveaux de c_card-1 (le plus proche) vers 0
        for level in range(c_card - 1, -1, -1):
            for di in level_index[level]:
                d_intent = concepts[di][0]

                # Rejet rapide : d doit être un sous-ensemble de c
                if (d_intent & c_intent) != d_intent:
                    continue

                # Test de domination par un parent déjà accepté
                dominated = False
                for p_intent in accepted_parents:
                    # d ⊂ p signifie que p est entre d et c (d au-dessus de p,
                    # p au-dessus de c), donc d n'est pas une couverture directe.
                    if (d_intent & p_intent) == d_intent and d_intent != p_intent:
                        dominated = True
                        break

                if not dominated:
                    accepted_parents.append(d_intent)
                    edges.append((ci, di))

    return edges


# ===================================================================
# Étape 10 — Génération du fichier DOT
# ===================================================================
#
# Numérotation des nœuds :
#   Les nœuds sont numérotés de 0 à n-1, dans l'ordre trié des concepts
#   (critère : (|intent|, valeur masque intent)).
#
# Ordre d'écriture :
#   1. En-tête : digraph G { rankdir=BT; }
#   2. Déclarations des nœuds dans l'ordre des identifiants.
#   3. Arêtes triées par (child_idx, parent_idx).
#   4. Fermeture : }
#
# Format des labels :
#   "{ID (I: X, E: Y)|own_attrs|own_objs}"
#   - I = cardinalité de l'intent COMPLET (pas seulement les propres).
#   - E = cardinalité de l'extent COMPLET.
#   - own_attrs : attributs propres (introduits au concept), séparés par \n.
#   - own_objs  : objets propres (introduits au concept), séparés par \n.
#   - Si une zone est vide, on la laisse vide (pas de texte).
#
# Couleurs :
#   - 0 objet propre affiché  → fillcolor=lightblue
#   - 1 objet propre affiché  → pas de fillcolor
#   - >1 objets propres        → fillcolor=orange
#
# Déterminisme :
#   Le tri des concepts et des arêtes garantit une sortie stable et
#   reproductible pour les mêmes données d'entrée.
# ===================================================================

def compute_own_labels(concepts, edges, attributes, objects):
    """
    Calcule les labels réduits (attributs et objets propres) de chaque concept.

    Attributs propres du concept c :
      intent(c) \\ ⋃{ intent(p) : p est un parent (couverture sup.) de c }

    Objets propres du concept c :
      extent(c) \\ ⋃{ extent(ch) : ch est un enfant (couverture inf.) de c }

    Returns : (own_attrs, own_objs) — listes de bitmasks, un par concept.
    """
    n = len(concepts)
    children_of = [[] for _ in range(n)]
    parents_of = [[] for _ in range(n)]

    for child_idx, parent_idx in edges:
        parents_of[child_idx].append(parent_idx)
        children_of[parent_idx].append(child_idx)

    own_attrs = [0] * n
    own_objs = [0] * n

    for i in range(n):
        c_intent, c_extent = concepts[i]

        # Attributs propres = intent moins l'union des intents des parents
        parent_intent_union = 0
        for pi in parents_of[i]:
            parent_intent_union |= concepts[pi][0]
        own_attrs[i] = c_intent & ~parent_intent_union

        # Objets propres = extent moins l'union des extents des enfants
        child_extent_union = 0
        for chi in children_of[i]:
            child_extent_union |= concepts[chi][1]
        own_objs[i] = c_extent & ~child_extent_union

    return own_attrs, own_objs


def write_dot(concepts, edges, output_path, attributes, objects):
    """
    Génère le fichier DOT du diagramme de Hasse du treillis des concepts.

    Parameters
    ----------
    concepts    : list[(int, int)]   — concepts (intent, extent)
    edges       : list[(int, int)]   — arêtes (child_idx, parent_idx)
    output_path : str                — chemin du fichier DOT de sortie
    attributes  : list[str]          — noms des attributs
    objects     : list[str]          — noms des objets
    """
    own_attrs, own_objs = compute_own_labels(concepts, edges, attributes, objects)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("digraph G { \n")
        f.write("\trankdir=BT;\n")

        # --- Nœuds ---
        for idx, (intent_mask, extent_mask) in enumerate(concepts):
            i_card = popcount(intent_mask)
            e_card = popcount(extent_mask)

            own_a_names = bitmask_to_names(own_attrs[idx], attributes)
            own_o_names = bitmask_to_names(own_objs[idx], objects)
            n_own_objs = len(own_o_names)

            # Construction des sections du label
            attr_str = "\\n".join(own_a_names)
            if attr_str:
                attr_str += "\\n"
            obj_str = "\\n".join(own_o_names)
            if obj_str:
                obj_str += "\\n"
            label = f"{{{idx} (I: {i_card}, E: {e_card})|{attr_str}|{obj_str}}}"

            # Couleur déterministe basée sur le nombre d'objets propres
            if n_own_objs == 0:
                colour = ",fillcolor=lightblue"
            elif n_own_objs > 1:
                colour = ",fillcolor=orange"
            else:
                colour = ""

            f.write(f'{idx} [shape=record,style=filled{colour},'
                    f'label="{label}"];\n')

        # --- Arêtes ---
        sorted_edges = sorted(edges, key=lambda e: (e[0], e[1]))
        for child_idx, parent_idx in sorted_edges:
            f.write(f"\t{child_idx} -> {parent_idx}\n")

        f.write("}\n")


# ===================================================================
# Main
# ===================================================================

def main():
    """
    Point d'entrée.  Lit le chemin CSV depuis la ligne de commande, calcule
    le treillis des concepts formels, et génère le fichier DOT.
    """
    if len(sys.argv) < 2:
        print("Usage: python lattice2.py <context.csv>", file=sys.stderr)
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print(f"Erreur : fichier introuvable : {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Dérivation du chemin de sortie : <csv_dir>/Lattice/<basename>_LLM_2.dot
    csv_dir = os.path.dirname(csv_path) or '.'
    basename = os.path.splitext(os.path.basename(csv_path))[0]
    output_path = os.path.join(csv_dir, "Lattice", f"{basename}_LLM_2.dot")
    partition_dir = os.path.join(csv_dir, PARTITION_DIR_NAME)

    # ---- Étape 1 : Chargement du contexte ----
    print(f"Chargement du contexte depuis {csv_path} ...")
    objects, attributes, obj_attrs, attr_objs, n_objs, n_attrs = \
        load_context(csv_path)
    all_objs = (1 << n_objs) - 1
    all_attrs = (1 << n_attrs) - 1
    print(f"  |G| = {n_objs} objets, |M| = {n_attrs} attributs")

    # ---- Taille de batch adaptative ----
    batch_size = compute_adaptive_batch_size(n_attrs, n_objs)
    print(f"  Taille de batch adaptative : {batch_size}")
    print(f"  RAM disponible : {get_available_memory_mb():.0f} Mo")

    # ---- Étapes 3-7 : Énumération des concepts ----
    print("Énumération des concepts (NextClosure avec partitionnement) ...")
    total = next_closure_partition(
        n_attrs, attr_objs, obj_attrs, all_objs, all_attrs,
        attributes, objects, partition_dir, batch_size
    )
    print(f"  {total} concepts énumérés.")

    # ---- Étape 8 : Rechargement et fusion ----
    print("Rechargement des partitions ...")
    concepts = load_partitions(partition_dir, attributes, objects)
    print(f"  {len(concepts)} concepts uniques après fusion.")

    # ---- Étape 9 : Calcul des arêtes ----
    print("Calcul de la relation de couverture ...")
    edges = compute_edges(concepts)
    print(f"  {len(edges)} arêtes.")

    # ---- Étape 10 : Génération du DOT ----
    print(f"Écriture du fichier DOT : {output_path} ...")
    write_dot(concepts, edges, output_path, attributes, objects)
    print("Terminé.")

    # ---- Nettoyage du répertoire de partitions ----
    shutil.rmtree(partition_dir, ignore_errors=True)

    return output_path


if __name__ == "__main__":
    main()
