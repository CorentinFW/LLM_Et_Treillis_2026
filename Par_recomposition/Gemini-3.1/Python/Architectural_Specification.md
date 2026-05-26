# Architectural Specification: Out-of-Core FCA Lattice Computation

## 1. Hypotheses and Scope

**Scope:**
This specification defines the logical architecture, data structures, and algorithmic strategies for a Python-based Formal Concept Analysis (FCA) lattice computation system. The system is designed to handle very large binary contexts that exceed available Random Access Memory (RAM) by leveraging decomposition, incremental processing, and efficient serialization.

**Hypotheses:**
- **H1 (Input Validity):** The input consists of valid CSV files representing formal contexts.
- **H2 (I/O Bottleneck):** Disk I/O operations are orders of magnitude slower than CPU operations. Sequential reads/writes are preferred over random access.
- **H3 (Sparsity/Density Unpredictability):** The density of the input incidence matrix is unknown. The algorithm must remain robust across both highly sparse and highly dense datasets.
- **H4 (Scale):** The number of concepts may grow exponentially relative to the input context size. The full lattice might not fit entirely in RAM, necessitating persistent intermediate storage.

**Assumptions & Trade-offs:**
- **Trade-off 1 (Memory vs. I/O):** To strictly bound RAM usage, the system will aggressively flush intermediate concept sets to disk, increasing disk I/O.
- **Trade-off 2 (CPU vs. Memory):** Duplicate detection across memory bounds requires cryptographic hashing and disk-based indexing to avoid loading all concepts into RAM, spending CPU cycles on hashing to save memory.
- **Trade-off 3 (Cover Relation):** Computing the cover relation out-of-core is highly inefficient; therefore, the lattice merge phase will maintain parent/child relationships incrementally.

---

## 2. Input/Output Contract Derived From Documentation

### 2.1 Input Contract (CSV Parsing)
**Mandatory Rules:**
1.  **Detection:** Auto-detect the delimiter (`;` or `,`).
2.  **Geometry:** Every row must have the same number of columns. There must be at least one header row and one data row.
3.  **Content:** The first column acts as the object identifier (row identifier). Columns 2 to $N$ represent attributes.
4.  **Values:** All attribute cells must strictly evaluate to integer `0` or `1`.
5.  **Sanitization:** Trim external whitespace and strip external quotation marks from all cells. The first header cell must be treated as empty or ignored.

**Invalid Cases & Rejections:**
- Varying column counts across rows.
- Non-binary values in columns 2 to $N$.
- Zero data rows or zero attribute columns.

### 2.2 Output Contract (DOT Generation)
**Mandatory Rules:**
1.  **Structure:** Must output a standard directed graph wrapped in `digraph G { ... }` with `rankdir=BT;`.
2.  **Node Format:** Each node must use sequential integer IDs (`0`, `1`, ...) and the `shape=record` attribute.
    -   **Label Schema:** `{<ID> (I: <intent_size>, E: <extent_size>)|<intent_lines>|<extent_lines>}`
    -   Attributes and objects within the label must be separated by `\n`.
3.  **Color Rules:**
    -   `fillcolor=lightblue` IF displayed extent size == 0.
    -   No `fillcolor` property IF displayed extent size == 1.
    -   `fillcolor=orange` IF displayed extent size > 1.
4.  **Edge Format:** `<source_id> -> <target_id>` (representing the cover relation, bottom-up).
5.  **Escaping:** Label strings must properly escape double quotes (`"`) and existing backslashes (`\`).

**Edge Cases to Handle:**
- Single node lattice (only one concept, no edges).
- Empty/degenerate logical lattice (output exactly: `digraph G { rankdir=BT; }`).
- 0-byte invalid files must be detected as failures, but not produced.

---

## 3. FCA Conceptual Model and Invariants

**Formal Definitions:**
-   **Context:** $\mathbb{K} = (G, M, I)$ where $G$ is the set of objects, $M$ is the set of attributes, and $I \subseteq G \times M$ is the binary incidence relation.
-   **Derivation Operators (Up/Down):**
    -   For $A \subseteq G$: $A^\uparrow = \{m \in M \mid \forall g \in A, (g, m) \in I\}$
    -   For $B \subseteq M$: $B^\downarrow = \{g \in G \mid \forall m \in B, (g, m) \in I\}$
-   **Closure Operator:** $A'' = (A^\uparrow)^\downarrow$ for objects, and $B'' = (B^\downarrow)^\uparrow$ for attributes.
-   **Formal Concept:** A pair $(A, B)$ where $A \subseteq G$, $B \subseteq M$, $A^\uparrow = B$, and $B^\downarrow = A$. $A$ is the extent, $B$ is the intent.
-   **Partial Order:** $(A_1, B_1) \le (A_2, B_2) \iff A_1 \subseteq A_2 \iff B_2 \subseteq B_1$.
-   **Cover Relation:** $C_1 \prec C_2$ iff $C_1 < C_2$ and there exists no concept $C_3$ such that $C_1 < C_3 < C_2$.

**Correctness Invariants:**
1.  **Closure Invariant:** Every generated concept $(A, B)$ MUST strictly satisfy $A^\uparrow = B$ and $B^\downarrow = A$.
2.  **Uniqueness Invariant:** For any two concepts $C_1 = (A_1, B_1)$ and $C_2 = (A_2, B_2)$, $C_1 \ne C_2 \iff A_1 \ne A_2 \iff B_1 \ne B_2$. No duplicate intents may exist in the final lattice.
3.  **Cover Invariant:** If $C_1 \prec C_2$ is an edge, no intermediate subset/superset concept exists.
4.  **Top/Bottom Invariant:** The lattice must have exactly one infimum (Bottom concept, extent $G^\uparrow{}^\downarrow$) and exactly one supremum (Top concept, intent $M^\downarrow{}^\uparrow$).

---

## 4. Proposed Logical Architecture

The system is decomposed into 5 autonomous pipelines:

1.  **Reader & Validator (I/O Bound):**
    -   Streams the CSV, detects delimiters, validates binary constraints, and extracts $G$ and $M$.
    -   Outputs a memory-mapped binary Incidence Matrix and chunked object sets.
2.  **Partitioned Concept Generator (Compute Bound):**
    -   Horizontally partitions the context $G$ into blocks.
    -   Computes formal concepts locally for each block using an optimized in-memory algorithm (e.g., algorithmic NextClosure or local AddIntent).
    -   Serializes local concepts to disk to clear RAM.
3.  **Global Merge & Deduplication (I/O & Compute Bound):**
    -   Pairs disk-persisted blocks.
    -   Computes the global concepts from local intents via intersection.
    -   Deduplicates concepts globally using intent-hashing and disk-based B-Trees/Hash indices.
4.  **Cover Relation Builder (Compute Bound):**
    -   Sorts unified concepts by intent size.
    -   Establishes edges incrementally to avoid $O(N^2)$ global comparisons.
5.  **DOT Emitter (I/O Bound):**
    -   Streams the final concepts and cover relations to disk.
    -   Applies all formatting, escaping, and node numbering rules deterministically.

---

## 5. Data Structures

### 5.1 RAM-Bound Structures
-   **Bitsets:** Attributes and extents are stored as high-performance integers/bit-arrays (e.g., Python `int` acts as a bit vector of arbitrary length).
    -   `intent_mask: int` (Length equals $|M|$).
    -   `extent_mask: int` (Length equals $|G|$).
-   **Local Trie / Hash Map:** Used during block-processing for local uniqueness checks.

### 5.2 Disk-Bound Structures
-   **Persistent Key-Value Store (e.g., LMDB, SQLite, or custom append-only log):**
    -   `Key`: SHA-256 hash or exact bitstring of the `intent_mask`.
    -   `Value`: `extent_mask` and a local sequential ID.
-   **Cover Edge Index:**
    -   A graph definition file mapping `source_id -> list[target_id]`.

---

## 6. Memory Decomposition Strategy

**Partitioning Strategy:**
Horizontal Partitioning: The context $\mathbb{K}$ is split by objects. If $G = \{g_1, \dots, g_N\}$, it is divided into $k$ disjoint partitions $G_1, G_2, \dots, G_k$ such that the local context for each partition easily fits in RAM (e.g., chunks of 1,000 to 10,000 rows depending on system memory).

**Adaptive RAM-aware Logic:**
-   Monitor RAM usage (via `psutil` or heuristics based on context width).
-   When usage exceeds 70% threshold, actively flush the current concept list to disk and clear RAM.

**Serialization Format:**
-   Uses binary serialization (e.g., protocol buffers or memory-mapped numpy arrays for bitsets).
-   Each flushed block $i$ becomes a file `block_i.bin`.

**Restart/Recovery Mechanism:**
-   Maintain an atomic `manifest.json` tracking the pipeline phase and completed blocks.
-   If interrupted, the system resumes from the last fully serialized step (e.g., block generation phase or merge phase).

---

## 7. Merge and Deduplication Strategy

**Incremental Merge Logic (Apposition):**
To merge two conceptual sub-lattices $L_1$ (from $G_1$) and $L_2$ (from $G_2$):
1.  Any intent $B \in L_1$ or $B \in L_2$ evaluated over $G_1 \cup G_2$ generates an intent.
2.  The set of global intents is exactly the pairwise intersection of intents from $L_1$ and $L_2$:
    $Intents(L_{1 \cup 2}) = \{ B_1 \cap B_2 \mid B_1 \in L_1, B_2 \in L_2 \} \cup Intents(L_1) \cup Intents(L_2)$
3.  Because memory is constrained, streams of intents from $L_1$ and $L_2$ are read from disk.
4.  Intersection is computed, and the new `intent_mask` is hashed.

**Deterministic Deduplication:**
1.  **Canonical Identity:** The boolean `intent_mask` (length $M$) serves as the unique universal identifier for a concept.
2.  **Stable Hash Index:** A persistent B-Tree stores `Hash(intent_mask) -> Concept_ID`. If a collision occurs (or exact match), the extents are merged with a bitwise OR (`extent_mask = extent_mask_1 | extent_mask_2`).
3.  **Stable Sorting:** After full global deduplication, concepts are sorted exactly by `intent_size` (descending) and then lexicographically by the `intent_mask` integer value.

---

## 8. Optimized Cover Relation Strategy

A naive implementation compares every concept against every other concept $O(|L|^2)$, mapping to $O(|L|^3)$ checks. This is strictly forbidden.

**Block-compatible Processing:**
1.  Group all final concepts by `intent_length = len(B)`.
2.  Process levels bottom-up (largest intent length to smallest).
3.  **Indexing:** Maintain a list of already-processed concepts.
4.  **Subset/Superset Acceleration:**
    -   To find covers for Concept $C_x$:
    -   Iterate over concepts $C_y$ where `intent_length(y) < intent_length(x)`.
    -   Check if $B_y \subset B_x$ using bitwise operation `(B_y & B_x) == B_y`.
    -   **Candidate Pruning:** Keep an active "Cover Mask" for $C_x$. When a valid parent $C_y$ is found, union $B_y$ into the Cover Mask. If another candidate $C_z$ is checked and `(B_z & Cover_Mask) == B_z`, then $C_z$ is already covered by a path through $C_y$ and CANNOT be a direct cover. Skip it. (This transitive reduction bypasses explicit intermediate-concept elimination loops).

---

## 9. DOT Specification (Labels, Colors, Ordering, Stability)

**1. Stable Node Numbering:**
Node IDs must be sequentially assigned from $0$ to $|L|-1$ based on the deterministic sort defined in Section 7.

**2. Compact Label Construction:**
Labels must safely join text using `\n`.
Extents displayed must be empty if the extent size is 0.

**3. Character Escaping Rules:**
Attributes and object names containing double quotes `"` must be escaped to `\"`. Backslashes `\` to `\\`.

**4. Color Assignment (Strictly Enforced):**
-   Extract `extent_size = popcount(extent_mask)`.
-   If `extent_size == 0`: inject `fillcolor=lightblue, style=filled`.
-   If `extent_size == 1`: use default style (omit `fillcolor`, omit `style=filled`).
-   If `extent_size > 1`: inject `fillcolor=orange, style=filled`.

**5. Edge Ordering:**
Edges must be sorted by `source_id` ascending, then `target_id` ascending, ensuring absolute stability of the text output.

**6. Formatting Template Example:**
```dot
<ID> [shape=record,style=filled,fillcolor=<color>,label="{<ID> (I: <intent_size>, E: <extent_size>)|<intent_newlines>|<extent_newlines>}"];
```
Note: If no color applies (size=1), remove `,style=filled,fillcolor=<color>`.

---

## 10. Pseudo-Code of Critical Components

**10.1 Bitwise Sub/Super Verification for Cover Relation**
```python
def compute_covers(sorted_concepts):
    # sorted_concepts is ordered by intent_size DESCENDING
    edges = []
    # For O(1) bitwise subset checks
    for idx, c_x in enumerate(sorted_concepts):
        # bitmask summarizing all attributes inherited from proven parents
        covered_attributes_mask = 0 
        
        # Look at potential parents (smaller intents)
        for c_y in sorted_concepts[idx+1:]:
            # Check if c_y is a strict subset
            if (c_y.intent_mask & c_x.intent_mask) == c_y.intent_mask:
                # Transitive reduction check: is c_y already covered?
                if (c_y.intent_mask & covered_attributes_mask) != c_y.intent_mask:
                    # Direct cover found!
                    edges.append((c_x.id, c_y.id))
                    # Mark c_y's attributes as covered
                    covered_attributes_mask |= c_y.intent_mask
                    
        # Optional early exit if covered_attributes_mask == c_x.intent_mask 
        # (Be careful with bottom concept specifics)
    return edges
```

**10.2 Strict DOT Generation Block**
```python
def generate_dot_node(c, id_map):
    c_id = id_map[c.intent_mask]
    ext_size = c.extent_size
    
    # Apply Color Rules
    color_attrs = ""
    if ext_size == 0:
        color_attrs = "style=filled,fillcolor=lightblue,"
    elif ext_size > 1:
        color_attrs = "style=filled,fillcolor=orange,"

    # Format Strings
    intent_str = "\\n".join(escape(attr) for attr in c.intents)
    extent_str = "\\n".join(escape(obj) for obj in c.extents)
    
    label = f"{{{c_id} (I: {c.intent_size}, E: {ext_size})|{intent_str}|{extent_str}}}"
    
    return f"{c_id} [shape=record,{color_attrs}label=\"{label}\"];"
```

---

## 11. Verification Plan and Acceptance Criteria

**Functional Test Plan:**
1.  **Small Contexts:** Test with standard matrices (e.g., 3x3 boolean matrix). Verify manual result.
2.  **Degenerate Contexts:** Verify $0 \times 0$, $N \times 0$ (all zeroes), and files with exactly 1 row. Ensure it outputs valid DOT logic.
3.  **Large Contexts:** Generate >100 MB randomized valid CSV Context to trigger block-partitioning. Ensure memory remains bounded < assigned quota.
4.  **Non-regression Checks:** Output DOTs for identical inputs must have `SHA-256(execution 1) == SHA-256(execution 2)`.

**Validation Rules (Automated):**
1.  `validate_fca()`: Ensure every generated node satisfies `intent == intent_closure(intent)` and `extent == extent_closure(extent)`.
2.  `validate_dot()`: Run Graphviz `dot -Tnone <output.dot>` to explicitly verify syntactic validity.
3.  `validate_transitivity()`: Path between $A$ and $B$ in output tree implies $B \subset A$. Check no direct edge exists if an intermediate node $C$ fulfills $B \subset C \subset A$.

---

## 12. Pre-Implementation Checklist

- [ ] Select internal bitmask integer format capable of unlimited width (Native Python integers fulfill this).
- [ ] Implement robust CSV Parser utilizing Python's `csv` module with Sniffer.
- [ ] Draft automated Unittest suite with 100% path coverage for DOT generation edge cases (Colors, empty extents, escaping).
- [ ] Select embedded KV Store module for disk persistence (e.g., Python standard library `sqlite3` or external `lmdb`).
- [ ] Define block size parameters and expose them as configurable CLI arguments for tuning memory consumption.
- [ ] Implement global application logger to capture failure states and partial partition saves.
- [ ] Ensure the implementation strictly maps identical IDs structurally regardless of machine state to maintain non-regression hashes.