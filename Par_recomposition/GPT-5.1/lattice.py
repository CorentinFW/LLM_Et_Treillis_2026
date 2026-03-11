import csv
import gc
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class Concept:
    """In-memory representation of a formal concept.

    The lattice itself is kept on disk during enumeration; we only
    instantiate Concept objects when reassembling partitions for
    edge computation and DOT generation.
    """

    id: int
    intent_mask: int
    extent_mask: int


def load_context(csv_path: str) -> Tuple[List[str], List[str], List[int]]:
    """Load a formal context from a CSV file.

    The CSV format is assumed to be:
        - first row: empty first cell, then attribute names
        - subsequent rows: first cell is object name, then 0/1 entries

    This function makes no assumptions on the number of objects |G|
    or attributes |M|. It returns:

        objects: list of object names (size |G|)
        attributes: list of attribute names (size |M|)
        attr_extents: list of bitmasks, one per attribute; for attribute j,
                      attr_extents[j] has bit i set iff object i has attribute j.

    Complexity:
        Time  O(|G| * |M|) to read and process every cell.
        Space O(|G| * |M| / word_size) bits for attr_extents.
    """

    objects: List[str] = []
    attributes: List[str] = []
    attr_extents: List[int]

    with open(csv_path, newline="", encoding="utf-8") as f:
        # Try to be robust w.r.t. delimiter; Animals11 uses ';'.
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[";", ",", "\t"])  # type: ignore[arg-type]
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"  # type: ignore[attr-defined]

        reader = csv.reader(f, dialect)

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("Empty CSV file: no header row found")

        if len(header) < 2:
            raise ValueError("CSV header must contain at least one attribute column")

        # First column is the object column header (often empty or a label like ';').
        attributes = [a.strip() for a in header[1:]]
        m = len(attributes)
        attr_extents = [0 for _ in range(m)]

        for obj_index, row in enumerate(reader):
            if not row:
                continue
            name = row[0].strip()
            if not name:
                name = f"obj_{obj_index}"
            objects.append(name)

            cells = row[1:]
            if len(cells) != m:
                raise ValueError(
                    f"Row for object '{name}' has {len(cells)} attribute cells, expected {m}"
                )

            for j, cell in enumerate(cells):
                v = cell.strip()
                if v == "1":
                    attr_extents[j] |= (1 << obj_index)
                # Other values are treated as 0 by default.

    return objects, attributes, attr_extents


def closure(
    intent_mask: int,
    attr_extents: List[int],
    all_objects_mask: int,
) -> Tuple[int, int]:
    """Compute the closure X'' of an attribute set X given as a bitmask.

    Returns (closed_intent_mask, extent_mask), where:
        - extent_mask is the set X' of objects sharing all attributes in X
        - closed_intent_mask is X'' = { attributes common to all objects in extent_mask }.

    Implementation:
        1. Compute extent_mask as the intersection of extents of attributes in X.
           If X is empty, extent_mask is all_objects_mask.
        2. An attribute j belongs to X'' iff extent_mask is a subset of attr_extents[j].

    Complexity:
        Let |G| be number of objects, |M| number of attributes.
        - Step 1: O(|X|) bitwise ANDs over |G| bits.
        - Step 2: O(|M|) bitwise checks.

        Using Python integers as bitsets, these are efficient and scale well
        until the bit-length exceeds available RAM.
    """

    m = len(attr_extents)

    # Step 1: compute extent X'.
    if intent_mask == 0:
        extent_mask = all_objects_mask
    else:
        extent_mask = all_objects_mask
        # Intersect extents of attributes present in intent_mask.
        mask = intent_mask
        j = 0
        while mask:
            if mask & 1:
                extent_mask &= attr_extents[j]
            mask >>= 1
            j += 1

    # Step 2: compute X'' as all attributes whose extent contains extent_mask.
    closed_intent_mask = 0
    for j, ext in enumerate(attr_extents):
        if extent_mask & ext == extent_mask:
            closed_intent_mask |= (1 << j)

    return closed_intent_mask, extent_mask


def _next_closure_step(
    current_intent: int,
    attr_extents: List[int],
    all_objects_mask: int,
) -> Optional[int]:
    """Internal: Ganter's NextClosure step on the full attribute set.

    Given the current closed intent (as a bitmask), compute the next closed
    intent in lectic order, or None if there is no next intent.

    Lectic order is induced by the fixed attribute ordering attributes[0] < ... < attributes[m-1].

    Complexity:
        For each step, in the worst case we try O(|M|) candidate attributes,
        and each candidate requires one closure computation, which is
        O(|M| + cost of extent intersection). Overall complexity is standard
        NextClosure complexity: polynomial in |G|, |M| per concept.
    """

    m = len(attr_extents)
    A = current_intent

    for i in range(m - 1, -1, -1):
        if not (A & (1 << i)):
            # Build candidate: (A restricted to attributes < i) union {i}.
            prefix_mask = A & ((1 << i) - 1)
            candidate = prefix_mask | (1 << i)
            B, _ = closure(candidate, attr_extents, all_objects_mask)

            # Lectic condition: for all j < i, if j is in B then j is in A.
            # Equivalently, (B & ((1<<i)-1)) has no bits outside A.
            lower_bits = B & ((1 << i) - 1)
            if lower_bits & ~A:
                continue
            return B

    return None


def next_closure_partition(
    attr_extents: List[int],
    all_objects_mask: int,
    partition_size: int,
) -> Iterable[Tuple[int, int]]:
    """Global NextClosure enumeration yielding (intent_mask, partition_index).

    This function enumerates all formal concepts (via their intents) using
    the standard NextClosure algorithm, independent of any partitioning.

    To obtain a *partitioned* computation, we assign each concept to a
    partition based on the index of its smallest attribute in lectic order.
    More precisely, for a concept intent with smallest attribute index i,
    we assign it to partition_index = i // partition_size.

    This induces a disjoint partition of the concept set by attribute blocks.
    Each concept is sent to exactly one partition, and all partitions together
    cover the whole lattice. During enumeration we never keep all concepts
    in RAM; each concept is immediately streamed to its partition on disk.

    Yields:
        (intent_mask, partition_index)
    """

    m = len(attr_extents)
    if m == 0:
        partition_index = 0
        closed_intent, _ = closure(0, attr_extents, all_objects_mask)
        yield closed_intent, partition_index
        return

    if partition_size <= 0:
        partition_size = max(1, m)

    # Start with closure of the empty set.
    current_intent, _ = closure(0, attr_extents, all_objects_mask)

    while True:
        # Determine partition by smallest attribute index present in the intent.
        intent_mask = current_intent
        if intent_mask == 0:
            # Edge case: truly empty intent (possible in degenerate contexts).
            partition_index = 0
        else:
            # Least significant set bit gives the smallest attribute index.
            lsb = intent_mask & -intent_mask
            first_index = lsb.bit_length() - 1
            partition_index = first_index // partition_size

        yield intent_mask, partition_index

        nxt = _next_closure_step(current_intent, attr_extents, all_objects_mask)
        if nxt is None:
            break
        current_intent = nxt


def _intent_to_names(intent_mask: int, attributes: List[str]) -> List[str]:
    names: List[str] = []
    j = 0
    mask = intent_mask
    while mask:
        if mask & 1:
            names.append(attributes[j])
        mask >>= 1
        j += 1
    return names


def _extent_from_intent(
    intent_mask: int,
    attr_extents: List[int],
    all_objects_mask: int,
) -> int:
    """Compute the extent X' from a *closed* intent X.

    For a closed intent X, we only need the intersection of attribute extents
    to obtain extent(X). We do not recompute the closure here.
    """

    if intent_mask == 0:
        return all_objects_mask

    extent_mask = all_objects_mask
    mask = intent_mask
    j = 0
    while mask:
        if mask & 1:
            extent_mask &= attr_extents[j]
        mask >>= 1
        j += 1
    return extent_mask


def _extent_to_names(extent_mask: int, objects: List[str]) -> List[str]:
    names: List[str] = []
    i = 0
    mask = extent_mask
    while mask:
        if mask & 1:
            names.append(objects[i])
        mask >>= 1
        i += 1
    return names


def save_partition(
    base_partition_dir: str,
    partition_index: int,
    concept_record: Dict[str, object],
) -> None:
    """Append a single concept record to the JSON lines file of a partition.

    Files are organized as:
        base_partition_dir/
            part0/concepts.json
            part1/concepts.json
            ...

    Each concepts.json file contains one JSON object per line, of the form:
        {"intent": [...], "extent": [...]}.

    This streaming strategy avoids keeping whole partitions in memory.
    """

    part_dir = os.path.join(base_partition_dir, f"part{partition_index}")
    os.makedirs(part_dir, exist_ok=True)
    path = os.path.join(part_dir, "concepts.json")

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(concept_record, ensure_ascii=False))
        f.write("\n")


def load_partitions(
    base_partition_dir: str,
    attributes: List[str],
    objects: List[str],
) -> List[Concept]:
    """Load all partition files and reconstruct Concept objects.

    We read each partition sequentially and build the in-memory list of
    concepts (intents and extents as bitmasks). For very large lattices,
    this step can still be memory-intensive; however, the enumeration
    phase itself remains disk-backed.

    A defensive de-duplication could be done by tracking seen intent masks,
    but since each concept is assigned to exactly one partition by the
    partitioning strategy, duplicates cannot occur in normal operation.
    """

    # Map attribute and object names back to indices.
    attr_index: Dict[str, int] = {name: i for i, name in enumerate(attributes)}
    obj_index: Dict[str, int] = {name: i for i, name in enumerate(objects)}

    concepts: List[Concept] = []

    if not os.path.isdir(base_partition_dir):
        return concepts

    part_dirs = [
        d
        for d in os.listdir(base_partition_dir)
        if os.path.isdir(os.path.join(base_partition_dir, d)) and d.startswith("part")
    ]

    # Sort part directories by numeric suffix for determinism.
    def _part_key(name: str) -> int:
        try:
            return int(name[4:])
        except ValueError:
            return 0

    for part_name in sorted(part_dirs, key=_part_key):
        path = os.path.join(base_partition_dir, part_name, "concepts.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                intent_names = data.get("intent", [])
                extent_names = data.get("extent", [])

                intent_mask = 0
                for name in intent_names:
                    j = attr_index.get(name)
                    if j is not None:
                        intent_mask |= (1 << j)

                extent_mask = 0
                for name in extent_names:
                    i = obj_index.get(name)
                    if i is not None:
                        extent_mask |= (1 << i)

                c = Concept(id=len(concepts), intent_mask=intent_mask, extent_mask=extent_mask)
                concepts.append(c)

    return concepts


def compute_edges(concepts: List[Concept]) -> List[Tuple[int, int]]:
    """Compute the cover relation (Hasse diagram edges) between concepts.

    We use intent inclusion as the lattice order:
        C <= D  iff  intent(C) subset of intent(D).

    In the DOT output we orient edges from more specific to more general
    concepts, i.e. from larger intents to smaller intents. This matches
    the direction used in FCA4J's Animals11.dot example.

    The cover relation A -> B holds iff:
        - intent(B) is a strict subset of intent(A), and
        - there is no intermediate concept C with intent(B) subset intent(C) subset intent(A).

    Complexity:
        Let N be the number of concepts.
        - In the worst case we need O(N^2) subset tests to find candidate
          comparable pairs.
        - For each candidate pair we may scan other concepts to check
          for intermediates, giving O(N^3) in the worst case.

        For small contexts (like Animals11) this is perfectly acceptable
        and yields a cover relation structurally equivalent to FCA4J.
    """

    n = len(concepts)
    intents = [c.intent_mask for c in concepts]

    # Precompute intent sizes for quick comparison.
    intent_sizes = [intents[i].bit_count() for i in range(n)]

    edges: List[Tuple[int, int]] = []

    for i in range(n):
        Ai = intents[i]
        for j in range(n):
            if i == j:
                continue
            Aj = intents[j]
            # We want edges from more specific (larger intent) to more general (smaller intent).
            if intent_sizes[i] <= intent_sizes[j]:
                continue
            # Check Aj subset Ai.
            if Aj & ~Ai:
                continue

            # Now candidate i -> j. Check that there is no k with Aj subset Ak subset Ai.
            is_cover = True
            for k in range(n):
                if k == i or k == j:
                    continue
                Ak = intents[k]
                if Ak & ~Ai:
                    continue  # Ak not subset of Ai
                if Aj & ~Ak:
                    continue  # Aj not subset of Ak
                if intent_sizes[j] < intent_sizes[k] < intent_sizes[i]:
                    is_cover = False
                    break

            if is_cover:
                edges.append((i, j))

    return edges


def _compute_gamma_mu_labels(
    concepts: List[Concept],
    attributes: List[str],
    objects: List[str],
) -> Tuple[List[List[str]], List[List[str]]]:
    """Compute attribute and object labels (gamma/mu) for each concept.

    For each attribute m, its gamma-concept is the smallest (w.r.t. intent
    size, hence highest in the lattice) concept whose intent contains m.
    We attach the attribute label m to that concept.

    For each object g, its mu-concept is the largest concept (maximal
    intent size) whose extent contains g. We attach the object label g
    to that concept.

    This yields compact labels similar to FCA4J: attributes and objects
    are introduced only once at characteristic concepts, while intent and
    extent sizes still describe the full closed sets.
    """

    n = len(concepts)
    m = len(attributes)
    g = len(objects)

    label_intent: List[List[str]] = [[] for _ in range(n)]
    label_extent: List[List[str]] = [[] for _ in range(n)]

    intent_masks = [c.intent_mask for c in concepts]
    extent_masks = [c.extent_mask for c in concepts]
    intent_sizes = [mask.bit_count() for mask in intent_masks]

    # Attributes: gamma labels (smallest intent containing the attribute).
    for attr_index, attr_name in enumerate(attributes):
        best_concept: Optional[int] = None
        best_size = math.inf
        bit = 1 << attr_index
        for idx, mask in enumerate(intent_masks):
            if mask & bit:
                size = intent_sizes[idx]
                if size < best_size:
                    best_size = size
                    best_concept = idx
        if best_concept is not None:
            label_intent[best_concept].append(attr_name)

    # Objects: mu labels (largest intent containing the object in its extent).
    for obj_index, obj_name in enumerate(objects):
        best_concept = None
        best_size = -1
        bit = 1 << obj_index
        for idx, mask in enumerate(extent_masks):
            if mask & bit:
                size = intent_sizes[idx]
                if size > best_size:
                    best_size = size
                    best_concept = idx
        if best_concept is not None:
            label_extent[best_concept].append(obj_name)

    return label_intent, label_extent


def _escape_label_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\"", "\\\"")


def write_dot(
    output_path: str,
    concepts: List[Concept],
    edges: List[Tuple[int, int]],
    attributes: List[str],
    objects: List[str],
) -> None:
    """Write the concept lattice in DOT format.

    Node format matches the Animals11.dot schema:

        ID [shape=record,style=filled[,fillcolor=...],
            label="{ID (I: |I|, E: |E|)|intent_labels|extent_labels}"];

    where intent_labels and extent_labels are newline-separated labels as
    computed by gamma/mu labeling, while I and E sizes are the full
    closed-set cardinalities.

    Edges are written as:
        source -> target

    with source having a strictly larger intent than target.
    """

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    label_intent, label_extent = _compute_gamma_mu_labels(concepts, attributes, objects)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("digraph G { \n")
        f.write("\trankdir=BT;\n")

        # Nodes
        for concept in concepts:
            idx = concept.id
            intent_size = concept.intent_mask.bit_count()
            extent_size = concept.extent_mask.bit_count()

            intent_labels = "\\n".join(_escape_label_text(s) for s in label_intent[idx])
            extent_labels = "\\n".join(_escape_label_text(s) for s in label_extent[idx])

            # Determine fillcolor: highlight nodes where at least one of
            # the gamma/mu label sets is empty. This approximates the
            # style used in the Animals11 example and emphasizes
            # structurally important concepts (bounds, joins, meets).
            has_intent_label = bool(label_intent[idx])
            has_extent_label = bool(label_extent[idx])
            if has_intent_label and has_extent_label:
                fillcolor_part = ""
            else:
                fillcolor_part = ",fillcolor=lightblue"

            label = f"{{{idx} (I: {intent_size}, E: {extent_size})|{intent_labels}|{extent_labels}}}"
            f.write(
                f"{idx} [shape=record,style=filled{fillcolor_part},label=\"{_escape_label_text(label)}\"];\n"
            )

        # Edges
        for src, tgt in edges:
            f.write(f"\t{src} -> {tgt}\n")

        f.write("}\n")


def main(argv: List[str]) -> None:
    if len(argv) != 2:
        print("Usage: python lattice.py <context.csv>")
        raise SystemExit(1)

    csv_path = argv[1]
    objects, attributes, attr_extents = load_context(csv_path)

    g = len(objects)
    m = len(attributes)
    all_objects_mask = (1 << g) - 1 if g > 0 else 0

    # Partition size heuristic: for small contexts, a single partition;
    # for larger ones, partitions of size ~sqrt(|M|) balance the number
    # of partitions and per-part size. This can be adjusted if memory
    # constraints are known more precisely.
    if m <= 32:
        partition_size = m or 1
    else:
        partition_size = max(1, int(math.sqrt(m)))

    base_dir = os.path.dirname(os.path.abspath(csv_path))
    partition_dir = os.path.join(base_dir, "partition")
    os.makedirs(partition_dir, exist_ok=True)

    # Remove any existing partition data for a clean recomputation.
    for name in os.listdir(partition_dir):
        path = os.path.join(partition_dir, name)
        if os.path.isdir(path) and name.startswith("part"):
            # Best-effort cleanup of old partitions.
            for root, _, files in os.walk(path, topdown=False):
                for fn in files:
                    try:
                        os.remove(os.path.join(root, fn))
                    except OSError:
                        pass
                try:
                    os.rmdir(root)
                except OSError:
                    pass

    # --- Phase 1: Enumerate concepts and stream them into partitions. ---
    for intent_mask, part_index in next_closure_partition(
        attr_extents, all_objects_mask, partition_size
    ):
        extent_mask = _extent_from_intent(intent_mask, attr_extents, all_objects_mask)
        intent_names = _intent_to_names(intent_mask, attributes)
        extent_names = _extent_to_names(extent_mask, objects)

        record = {
            "intent": intent_names,
            "extent": extent_names,
        }
        save_partition(partition_dir, part_index, record)

    # We no longer need intermediate local variables related only to
    # enumeration; explicit deletion and garbage collection help free
    # memory before we reassemble the lattice.
    gc.collect()

    # --- Phase 2: Reassemble concepts from partitions. ---
    concepts = load_partitions(partition_dir, attributes, objects)

    # If for some reason a partition file was empty (e.g. no concepts
    # mapped to it), we may have lost the extent information; in that
    # case we recompute extent masks from the context for safety.
    if any(c.extent_mask == 0 and c.intent_mask != 0 for c in concepts) or not concepts:
        for c in concepts:
            c.extent_mask = _extent_from_intent(c.intent_mask, attr_extents, all_objects_mask)

    # Ensure deterministic IDs: concept.id is its index in the list.
    for idx, c in enumerate(concepts):
        c.id = idx

    # --- Phase 3: Compute cover relation and DOT output. ---
    edges = compute_edges(concepts)

    lattice_dir = os.path.join(base_dir, "Lattice")
    os.makedirs(lattice_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(csv_path))[0]
    dot_path = os.path.join(lattice_dir, f"{base_name}_LLM.dot")

    write_dot(dot_path, concepts, edges, attributes, objects)

    print(f"Wrote lattice DOT to: {dot_path}")


if __name__ == "__main__":
    main(sys.argv)
