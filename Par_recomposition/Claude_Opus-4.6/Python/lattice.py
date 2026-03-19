#!/usr/bin/env python3
"""
Formal Concept Analysis — Lattice computation with memory-efficient partitioning.

Computes all formal concepts and the covering relation (Hasse diagram) of the
concept lattice from a binary formal context stored in a CSV file.

Strategy:
  - Uses Ganter's NextClosure algorithm for lectic enumeration of all closed
    attribute sets (concept intents).
  - Partitions the output into batches written to disk, freeing memory between
    batches.  Each batch corresponds to a contiguous segment of the lectic order
    over attribute sets.
  - After enumeration, reloads and merges partitions, computes the covering
    relation, determines own (reduced) labels, and generates a DOT file.

Assumptions:
  - CSV delimiter is semicolon (;).
  - Cell values are in {0, 1}.
  - The first row contains attribute names (first cell empty or ignored).
  - The first column contains object names.
  - The context fits in memory (objects × attributes matrix); only the growing
    concept list is flushed to disk.

Complexity notes (|G| = objects, |M| = attributes, |L| = number of concepts):
  - Context loading:  O(|G| × |M|)
  - Closure X'':      O(|G| + |M|) per call (bitwise operations on big ints)
  - NextClosure:      O(|L| × |M|) closure calls  →  O(|L| × |M| × (|G|+|M|))
  - Edge computation: O(|L|² × |M| / word_size)  (pairwise bitmask subset tests)
  - DOT generation:   O(|L| + |edges|)

Usage:
    python lattice.py <context.csv>

Output:
    Lattice/<basename>_LLM.dot
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

# Number of concepts per partition batch.  Keeps peak memory bounded: at most
# BATCH_SIZE concept tuples are held in RAM at any time during enumeration.
BATCH_SIZE = 1000

# Partition working directory (relative to CSV location).
PARTITION_DIR_NAME = "partition"


# ===================================================================
# Helpers — bitset utilities
# ===================================================================

def popcount(mask):
    """Return the number of set bits in *mask*."""
    return bin(mask).count('1')


def bitmask_to_names(mask, names):
    """Convert a bitmask to the list of corresponding names, preserving order."""
    result = []
    for i, name in enumerate(names):
        if mask & (1 << i):
            result.append(name)
    return result


def names_to_bitmask(name_list, name_to_idx):
    """Convert a list of names back to a bitmask."""
    mask = 0
    for name in name_list:
        mask |= (1 << name_to_idx[name])
    return mask


# ===================================================================
# Étape 1 — Chargement du contexte formel
# ===================================================================

def load_context(csv_path):
    """
    Parse a formal context from a semicolon-delimited CSV file.

    Returns
    -------
    objects    : list[str]          – object names, row order preserved
    attributes : list[str]          – attribute names, column order preserved
    obj_attrs  : list[int]          – obj_attrs[g] is the bitmask of attributes
                                      possessed by object g
    attr_objs  : list[int]          – attr_objs[m] is the bitmask of objects
                                      possessing attribute m
    n_objs     : int
    n_attrs    : int

    Complexity: O(|G| × |M|) time and space.
    """
    objects = []
    attributes = []
    obj_attrs = []

    with open(csv_path, 'r', newline='', encoding='utf-8') as fh:
        reader = csv.reader(fh, delimiter=';')
        header = next(reader)
        # First cell is empty or contains a label — skip it.
        attributes = [a.strip() for a in header[1:]]
        n_attrs = len(attributes)

        for row in reader:
            if not row or all(c.strip() == '' for c in row):
                continue  # skip blank lines
            obj_name = row[0].strip()
            objects.append(obj_name)
            mask = 0
            for j in range(n_attrs):
                val = row[1 + j].strip() if (1 + j) < len(row) else '0'
                if val == '1':
                    mask |= (1 << j)
            obj_attrs.append(mask)

    n_objs = len(objects)

    # Pre-compute column bitmasks: attr_objs[m] = set of objects having attr m.
    attr_objs = [0] * n_attrs
    for g in range(n_objs):
        m = 0
        tmp = obj_attrs[g]
        while tmp:
            if tmp & 1:
                attr_objs[m] |= (1 << g)
            tmp >>= 1
            m += 1

    return objects, attributes, obj_attrs, attr_objs, n_objs, n_attrs


# ===================================================================
# Étape 2 — Opérateur de fermeture (closure)
# ===================================================================

def prime_attrs(attr_set, attr_objs, all_objs):
    """
    Compute X' — the set of objects that possess **all** attributes in X.

    Parameters
    ----------
    attr_set : int   – bitmask of attributes
    attr_objs : list – column bitmasks
    all_objs : int   – bitmask with all object bits set

    Returns
    -------
    int – bitmask of objects

    Complexity: O(|M|) — one AND per attribute in X.
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
    Compute Y' — the set of attributes shared by **all** objects in Y.

    Parameters
    ----------
    obj_set   : int   – bitmask of objects
    obj_attrs : list  – row bitmasks
    all_attrs : int   – bitmask with all attribute bits set

    Returns
    -------
    int – bitmask of attributes

    Complexity: O(|G|) — one AND per object in Y.
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
    Compute the double-prime closure X'' and the intermediate extent X'.

    Returns (intent, extent) as bitmask pair.

    Complexity: O(|G| + |M|).
    """
    extent = prime_attrs(attr_set, attr_objs, all_objs)
    intent = prime_objs(extent, obj_attrs, all_attrs)
    return intent, extent


# ===================================================================
# Étape 3 — NextClosure (Ganter)
# ===================================================================

def next_closure(current_intent, n_attrs, attr_objs, obj_attrs, all_objs, all_attrs):
    """
    Compute the next closed attribute set after *current_intent* in lectic
    (lexicographic-closure) order.

    Algorithm (Ganter 1984):
        For i from |M|-1 down to 0:
            if m_i ∉ current_intent:
                C = (current_intent ∩ {m_0,…,m_{i-1}}) ∪ {m_i}
                D = C''
                if D ∩ {m_0,…,m_{i-1}} == current_intent ∩ {m_0,…,m_{i-1}}:
                    return (D_intent, D_extent)   — this is the next closed set
            # otherwise, continue with next smaller i

    Returns
    -------
    (intent, extent) or None if enumeration is complete.

    Why this enumerates all concepts:
        The lectic order is a total order on all subsets of M.  The closure
        operator X ↦ X'' maps every subset to a closed set.  NextClosure jumps
        from one closed set to the next in this total order, skipping all
        non-closed subsets.  The canonicity test (checking the prefix) ensures
        each closed set is produced exactly once.  The enumeration starts at ∅''
        and ends at M (or the last closed set before M if M itself isn't reached).

    Complexity: O(|M|) closure calls per invocation, each O(|G|+|M|).
    """
    for i in range(n_attrs - 1, -1, -1):
        bit_i = 1 << i
        if not (current_intent & bit_i):
            # Candidate: keep prefix < i from current, add i
            prefix_mask = (1 << i) - 1  # bits 0 .. i-1
            candidate = (current_intent & prefix_mask) | bit_i
            d_intent, d_extent = closure(candidate, attr_objs, obj_attrs,
                                         all_objs, all_attrs)
            # Canonicity: the prefix before position i must be unchanged
            if (d_intent & prefix_mask) == (current_intent & prefix_mask):
                return d_intent, d_extent
    return None


# ===================================================================
# Étape 4 & 7 — Partition-based enumeration (main loop)
# ===================================================================

def next_closure_partition(n_attrs, attr_objs, obj_attrs, all_objs, all_attrs,
                           attributes, objects, partition_dir, batch_size=BATCH_SIZE):
    """
    Enumerate **all** formal concepts via NextClosure in lectic order, writing
    them to disk in partition batches of size *batch_size*.

    Partitioning strategy
    ---------------------
    NextClosure explores the attribute space in lectic order — a total order
    defined over the power set of M.  The lectic order is intrinsically tied to
    the sequential ordering of attributes: early segments of the enumeration
    correspond to concepts whose intents involve the first (lowest-index)
    attributes, while later segments involve higher-index attributes.

    We partition the *output stream* into contiguous segments of at most
    *batch_size* concepts.  Because the lectic order is deterministic, each
    partition corresponds to a well-defined contiguous region of the lectic
    attribute space.  After writing a partition, the concept list is freed and
    gc.collect() is called, bounding peak memory to O(batch_size) concepts
    plus the fixed-size context matrix.

    This guarantees:
    - **Exhaustiveness**: NextClosure is proven to produce every closed set
      exactly once.
    - **No duplicates**: lectic order is a total order; each concept appears
      in exactly one batch.
    - **Memory bound**: at most batch_size concepts in RAM at any time.

    How partition size adapts to available memory:
        *batch_size* can be tuned.  For very large contexts, a smaller value
        (e.g. 200) keeps memory low at the cost of more disk I/O.  For small
        contexts the default (1000) is more than sufficient.

    Parameters
    ----------
    partition_dir : str – directory where partition sub-folders are created.

    Returns
    -------
    int – total number of concepts enumerated.
    """
    n_objs = len(objects)

    # Ensure a clean partition directory
    if os.path.exists(partition_dir):
        shutil.rmtree(partition_dir)
    os.makedirs(partition_dir)

    # --- First concept: closure of the empty set (top of lattice) ---
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

        # --- Flush partition to disk when buffer is full ---
        if len(buffer) >= batch_size:
            part_path = os.path.join(partition_dir, f"part{part_idx}")
            save_partition(buffer, part_path, attributes, objects, n_attrs, n_objs)
            part_idx += 1
            # Étape 6 — Free memory
            del buffer
            gc.collect()
            buffer = []

    # Flush remaining concepts
    if buffer:
        part_path = os.path.join(partition_dir, f"part{part_idx}")
        save_partition(buffer, part_path, attributes, objects, n_attrs, n_objs)
        del buffer
        gc.collect()

    return total


# ===================================================================
# Étape 5 — Écriture sur disque (partition serialization)
# ===================================================================

def save_partition(concepts, partition_path, attributes, objects, n_attrs, n_objs):
    """
    Serialize a list of (intent_mask, extent_mask) concept pairs to a JSON
    file inside *partition_path*.

    JSON format (array of objects):
        [
          { "intent": ["attr1", "attr2"], "extent": ["obj1"] },
          ...
        ]

    Writing strategy:
        We write the complete batch at once (json.dump) rather than streaming
        individual records.  Since the batch size is bounded by BATCH_SIZE,
        the serialized JSON is always of controlled size.

    Complexity: O(batch_size × (|G| + |M|)) for bitmask→name conversion.
    """
    os.makedirs(partition_path, exist_ok=True)
    records = []
    for intent_mask, extent_mask in concepts:
        records.append({
            "intent": bitmask_to_names(intent_mask, attributes),
            "extent": bitmask_to_names(extent_mask, objects),
        })
    filepath = os.path.join(partition_path, "concepts.json")
    with open(filepath, 'w', encoding='utf-8') as fh:
        json.dump(records, fh, ensure_ascii=False)
    # Free the records list immediately.
    del records


# ===================================================================
# Étape 6 — Libération mémoire
# ===================================================================
#
# Memory release is performed at two points:
#
# 1. After each partition batch in next_closure_partition():
#       del buffer        — drops the list of (intent, extent) tuples
#       gc.collect()      — forces collection of any reference cycles
#
# 2. After partition loading in load_partitions():
#       del raw_data      — drops the parsed JSON after converting back
#                           to bitmasks
#       gc.collect()
#
# Variables that MUST stay in memory throughout:
#   - obj_attrs, attr_objs  (the context matrix — required for closure)
#   - attributes, objects   (name lists — required for I/O)
#
# Variables that are released between partitions:
#   - buffer / concepts     (the batch of concept tuples)
#   - records / raw_data    (serialised / deserialised JSON)


# ===================================================================
# Étape 8 — Recomposition des partitions
# ===================================================================

def load_partitions(partition_dir, attributes, objects):
    """
    Reload all partition files, merge, deduplicate, and sort concepts.

    Deduplication is performed via a set of (intent_mask, extent_mask) tuples.
    Although NextClosure already guarantees uniqueness, this step provides
    safety against implementation errors or interrupted runs.

    Sorting is by (|intent|, intent_mask) to ensure deterministic, reproducible
    node numbering in the DOT output.

    Returns
    -------
    list of (intent_mask, extent_mask) – sorted, deduplicated concepts.
    """
    attr_idx = {a: i for i, a in enumerate(attributes)}
    obj_idx = {o: i for i, o in enumerate(objects)}

    seen = set()
    concepts = []

    # Enumerate partition directories in numeric order
    part_dirs = sorted(
        [d for d in os.listdir(partition_dir)
         if os.path.isdir(os.path.join(partition_dir, d))],
        key=lambda d: int(d.replace("part", ""))
    )

    for pdir in part_dirs:
        filepath = os.path.join(partition_dir, pdir, "concepts.json")
        if not os.path.isfile(filepath):
            continue
        with open(filepath, 'r', encoding='utf-8') as fh:
            raw_data = json.load(fh)
        for rec in raw_data:
            i_mask = names_to_bitmask(rec["intent"], attr_idx)
            e_mask = names_to_bitmask(rec["extent"], obj_idx)
            key = (i_mask, e_mask)
            if key not in seen:
                seen.add(key)
                concepts.append(key)
        # Étape 6 — free raw partition data
        del raw_data
        gc.collect()

    # Deterministic sort: by (intent cardinality, intent bitmask value)
    concepts.sort(key=lambda c: (popcount(c[0]), c[0]))
    return concepts


# ===================================================================
# Étape 9 — Calcul des arêtes du treillis (covering relation)
# ===================================================================

def compute_edges(concepts):
    """
    Compute the covering (Hasse) relation of the concept lattice.

    Definition:
        Concept d *covers* concept c  (c ≺ d)  iff:
            intent(c) ⊃ intent(d)           (c is *below* d in the lattice)
            and there is no concept e with   intent(c) ⊃ intent(e) ⊃ intent(d).

    In the Hasse diagram (rankdir=BT), edges go from the *lower* concept (c)
    to its *upper cover* (d):  c → d.

    Algorithm:
        1. Concepts are already sorted by |intent| ascending (top first).
        2. For each concept c, we search for its **upper covers** — concepts d
           with intent(d) ⊂ intent(c) (i.e. d has *fewer* attributes, so d is
           *above* c in the lattice).
        3. Among all d with intent(d) ⊂ intent(c), we keep only the *maximal*
           intents (closest to c from above).  A candidate d is maximal iff no
           other candidate d' has intent(d) ⊂ intent(d') ⊂ intent(c).
        4. We iterate candidates in *descending* intent-size order and greedily
           accept a candidate unless it is dominated by an already-accepted one.

    Returns
    -------
    list of (child_idx, parent_idx) – edges from lower to upper concept.

    Complexity: O(|L|² × |M|/w) where w is the machine word size (64).
    """
    n = len(concepts)
    edges = []

    for ci in range(n):
        c_intent = concepts[ci][0]
        c_size = popcount(c_intent)

        # Collect candidates: concepts d with intent(d) ⊂ intent(c)
        # They have fewer attributes → smaller popcount → earlier in sorted list.
        candidates = []
        for di in range(n):
            if di == ci:
                continue
            d_intent = concepts[di][0]
            d_size = popcount(d_intent)
            if d_size >= c_size:
                continue  # d has at least as many attributes → not a superconcept
            # Check proper subset: d_intent ⊂ c_intent
            if (d_intent & c_intent) == d_intent:
                candidates.append((d_size, di, d_intent))

        # Sort candidates by intent size DESCENDING (largest proper subset first)
        candidates.sort(key=lambda x: -x[0])

        # Greedily select upper covers (maximal proper subsets)
        parents = []
        for _, di, d_intent in candidates:
            dominated = False
            for p_intent in parents:
                # If d_intent ⊂ p_intent, then p is between d and c
                # (d is above p which is above c) — so d is NOT an upper cover of c.
                # Wait — d has fewer attributes than p (we process descending).
                # d_intent ⊂ p_intent means d is above p.  p is already accepted
                # as an upper cover of c.  So d is NOT a *direct* upper cover.
                if (d_intent & p_intent) == d_intent and d_intent != p_intent:
                    dominated = True
                    break
            if not dominated:
                parents.append(d_intent)
                edges.append((ci, di))  # ci (below) → di (above)

    return edges


# ===================================================================
# Étape 10 — Génération du fichier DOT
# ===================================================================

def compute_own_labels(concepts, edges, attributes, objects):
    """
    Compute reduced (own) labels for each concept.

    Own attributes of concept c:
        intent(c)  ∖  ⋃{ intent(p) : p is a parent (upper cover) of c }

        i.e. attributes in c's intent that do NOT appear in any parent's intent.
        These are the attributes *introduced* at c.

    Own objects of concept c:
        extent(c)  ∖  ⋃{ extent(ch) : ch is a child (lower cover) of c }

        i.e. objects in c's extent that do NOT appear in any child's extent.
        These are the objects *introduced* at c.

    Returns
    -------
    own_attrs : list[int]  – bitmask of own attributes per concept
    own_objs  : list[int]  – bitmask of own objects per concept
    """
    n = len(concepts)
    # Build parent / child adjacency from edge list
    children_of = [[] for _ in range(n)]  # children_of[i] = list of child indices
    parents_of = [[] for _ in range(n)]   # parents_of[i] = list of parent indices

    for child_idx, parent_idx in edges:
        parents_of[child_idx].append(parent_idx)
        children_of[parent_idx].append(child_idx)

    own_attrs = [0] * n
    own_objs = [0] * n

    for i in range(n):
        c_intent, c_extent = concepts[i]

        # Own attributes = intent(c) minus union of parents' intents
        parent_intent_union = 0
        for pi in parents_of[i]:
            parent_intent_union |= concepts[pi][0]
        own_attrs[i] = c_intent & ~parent_intent_union

        # Own objects = extent(c) minus union of children's extents
        child_extent_union = 0
        for chi in children_of[i]:
            child_extent_union |= concepts[chi][1]
        own_objs[i] = c_extent & ~child_extent_union

    return own_attrs, own_objs


def write_dot(concepts, edges, output_path, attributes, objects):
    """
    Generate the DOT file representing the Hasse diagram of the concept lattice.

    Node format
    -----------
        ID [shape=record,style=filled,FILLCOLOR,label="{ID (I: X, E: Y)|own_attrs|own_objs}"];

    Fill-colour rules (based on number of own objects displayed):
        - 0 own objects  → fillcolor=lightblue
        - 1 own object   → no explicit fillcolor (default)
        - >1 own objects → fillcolor=orange

    Edge format
    -----------
        child_ID -> parent_ID

    Determinism:
        - Nodes are numbered 0..n-1 in the sorted concept order.
        - Edges are written in (child, parent) numeric order.
        - Attribute / object names within labels follow the original CSV order.

    Complexity: O(|L| + |edges|).
    """
    own_attrs, own_objs = compute_own_labels(concepts, edges, attributes, objects)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("digraph G { \n")
        f.write("\trankdir=BT;\n")

        # --- Nodes ---
        for idx, (intent_mask, extent_mask) in enumerate(concepts):
            i_card = popcount(intent_mask)
            e_card = popcount(extent_mask)

            own_a_names = bitmask_to_names(own_attrs[idx], attributes)
            own_o_names = bitmask_to_names(own_objs[idx], objects)

            n_own_objs = len(own_o_names)

            # Build label string
            attr_str = "\\n".join(own_a_names)
            if attr_str:
                attr_str += "\\n"
            obj_str = "\\n".join(own_o_names)
            if obj_str:
                obj_str += "\\n"
            label = f"{{{idx} (I: {i_card}, E: {e_card})|{attr_str}|{obj_str}}}"

            # Colour
            if n_own_objs == 0:
                colour = ",fillcolor=lightblue"
            elif n_own_objs > 1:
                colour = ",fillcolor=orange"
            else:
                colour = ""

            f.write(f'{idx} [shape=record,style=filled{colour},'
                    f'label="{label}"];\n')

        # --- Edges ---
        # Sort edges for deterministic output
        sorted_edges = sorted(edges, key=lambda e: (e[0], e[1]))
        for child_idx, parent_idx in sorted_edges:
            f.write(f"\t{child_idx} -> {parent_idx}\n")

        f.write("}\n")


# ===================================================================
# Main
# ===================================================================

def main():
    """
    Entry point.  Reads the CSV path from the command line, computes the
    formal concept lattice, and writes the DOT file.
    """
    if len(sys.argv) < 2:
        print("Usage: python lattice.py <context.csv>", file=sys.stderr)
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Derive output path:  Lattice/<basename>_LLM.dot
    csv_dir = os.path.dirname(csv_path) or '.'
    basename = os.path.splitext(os.path.basename(csv_path))[0]
    output_path = os.path.join(csv_dir, "Lattice", f"{basename}_LLM.dot")
    partition_dir = os.path.join(csv_dir, PARTITION_DIR_NAME)

    # Increase recursion limit for safety (not used by NextClosure which is
    # iterative, but guards against deep call stacks in edge computation).
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))

    # ---- Step 1: Load context ----
    print(f"Loading context from {csv_path} ...")
    objects, attributes, obj_attrs, attr_objs, n_objs, n_attrs = \
        load_context(csv_path)
    all_objs = (1 << n_objs) - 1
    all_attrs = (1 << n_attrs) - 1
    print(f"  |G| = {n_objs} objects, |M| = {n_attrs} attributes")

    # ---- Steps 3-7: Enumerate concepts with partitioning ----
    print("Enumerating concepts (NextClosure) ...")
    total = next_closure_partition(
        n_attrs, attr_objs, obj_attrs, all_objs, all_attrs,
        attributes, objects, partition_dir, BATCH_SIZE
    )
    print(f"  {total} concepts enumerated.")

    # ---- Step 8: Reload and merge partitions ----
    print("Reloading partitions ...")
    concepts = load_partitions(partition_dir, attributes, objects)
    print(f"  {len(concepts)} unique concepts after merge.")

    # ---- Step 9: Compute edges ----
    print("Computing covering relation ...")
    edges = compute_edges(concepts)
    print(f"  {len(edges)} edges.")

    # ---- Step 10: Generate DOT ----
    print(f"Writing DOT file to {output_path} ...")
    write_dot(concepts, edges, output_path, attributes, objects)
    print("Done.")

    # ---- Cleanup partition directory ----
    shutil.rmtree(partition_dir, ignore_errors=True)

    return output_path


if __name__ == "__main__":
    main()
