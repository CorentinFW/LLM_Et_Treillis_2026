You are an expert in **Formal Concept Analysis (FCA)** and **Python algorithm design**.

Your task is to design a **memory-efficient FCA lattice computation algorithm** in Python using a **partitioned computation strategy**.

You must reason step-by-step and explain each design decision before writing code.

The algorithm must compute the **concept lattice** of **any** binary formal context stored in a CSV file formatted like Animals11.csv, **for CSV files of arbitrary size** (from very small to very large).

Animals11.csv is **only an example of input format and a test case**. The algorithm must work for **any valid formal context CSV**, without assuming any particular list of objects, attributes, or fixed sizes.

For small contexts (e.g. Animals11.csv and other small examples), the lattice you compute (concepts, intents, extents, and cover relation) must be **extensionally equivalent** to the lattices computed by **FCA4J**, and the DOT output must match FCA4J's structure (up to irrelevant renamings like node IDs or ordering).

The output must be a DOT file whose **format and structure follow the same DOT schema as Animals11.dot**, but whose actual nodes and edges depend on the specific input context.

---

# GLOBAL OBJECTIVE

Implement a Python algorithm that:

1. Reads a CSV formal context of **arbitrary size** (do not hard-code anything specific to Animals11.csv)
2. Computes all formal concepts
3. Computes the lattice relations
4. Splits the computation into partitions
5. Saves each partition to disk
6. Frees RAM between partitions
7. Reassembles partitions
8. Outputs:

Lattice/<input_filename>_LLM.dot

The algorithm must:

* Work correctly for **small contexts**, producing lattices equivalent to FCA4J (e.g. the Animals11 example)
* Scale to **large CSV files** that may not fit fully in RAM, thanks to the partitioned strategy

---

# INPUT FORMAT

The CSV file is a **formal context**:

* First row = attributes
* First column = objects
* Values ∈ {0,1}

Example:

;flies;nocturnal;feathered
bat;1;1;0
ostrich;0;0;1

Interpretation:

G = objects
M = attributes
I = incidence relation

The CSV may contain **any number of objects and attributes**. Animals11.csv is just an example; your algorithm must **generalize to arbitrary contexts** without any size-dependent assumptions.

---

# OUTPUT FORMAT

The algorithm must produce a DOT file:

Lattice/<filename>_LLM.dot

Format:

digraph G {
rankdir=BT;

<node definitions>

<edges>
}

Node format:

ID [shape=record,style=filled,label="{ID (I: X, E: Y)|intent|extent}"];

Where:

ID = concept id
I = size(intent)
E = size(extent)

Intent attributes separated by newline
Extent objects separated by newline

Edges represent the **cover relation** of the lattice.

The algorithm must **not duplicate attributes or objects across concept labels** beyond what is implied by the formal concepts themselves. In the DOT output, each concept's intent and extent must correspond exactly to the closed sets of the FCA lattice, without re‑listing all objects/attributes at every node as in the “bad” example. For Animals11, the structure must be similar to the compact FCA4J output, not the verbose version where every node repeats all inherited attributes/objects.

The algorithm must also correctly generate **all necessary intermediate concepts** (including "empty" or "join" concepts with empty intent or empty extent) so that the Hasse diagram is complete and contains the "lightblue" nodes (like 0, 1, 3, 4, etc. in the provided target example for Animals11) required to correctly join other concepts.

For **small contexts** where a reference lattice exists (e.g. Animals11.dot from FCA4J), the set of nodes (intents/extents) and edges (cover relation) must correspond exactly to the FCA4J result, up to node numbering and order.

---

# MEMORY CONSTRAINT

The algorithm must NOT keep the full lattice in RAM.

Instead it must:

1. Compute a subset of concepts
2. Save them to disk
3. Free memory
4. Continue

This constraint is critical for handling very large CSV contexts that may exceed available memory.

---

# PARTITION STRATEGY

Concepts must be computed **by attribute partitions**.

Example:

If there are N attributes:

Partition 1:
attributes 1..k

Partition 2:
attributes k+1..2k

etc.

Each partition corresponds to:

partition/partX/

Files:

partition/partX/concepts.json

Each file contains:

* intents
* extents

Example JSON:

[
{
"intent":["flies","feathered"],
"extent":["bat"]
}
]

You must explain how the partition size (k) can be chosen or adapted based on the number of attributes and possibly memory constraints.

---

# REQUIRED REASONING STEPS

You MUST reason explicitly through these steps:

---

## Step 1 — Formal Context Loading

Explain:

* How CSV is parsed, without assuming a fixed number of rows or columns
* Data structures used

Use:

objects list
attributes list
binary matrix

Explain complexity in terms of |G| (number of objects) and |M| (number of attributes).

---

## Step 2 — Closure Operator

Explain how to implement:

closure(X) = X''

Algorithm:

1 get objects having attributes X
2 compute common attributes

Explain complexity in terms of |G| and |M|.

---

## Step 3 — Concept Enumeration

Design a NextClosure-like algorithm.

Explain:

* lexicographic order
* intent generation
* closure usage
* stopping condition

Explain complexity.

---

## Step 4 — Partitioned Enumeration

Design a partitioned enumeration:

Explain:

* how to split attribute search space into partitions that cover all attributes
* how to guarantee no duplicates across partitions
* how to cover all concepts
* how the approach scales when |M| grows

Explain carefully.

---

## Step 5 — Disk Storage

Explain:

* folder creation

partition/
partition/part1/
partition/part2/

Explain:

* JSON format
* writing strategy (e.g. streaming or batched writes) for large outputs

---

## Step 6 — Memory Release

Explain:

* which variables must be deleted
* use of:

del variable
gc.collect()

Explain when memory is released and why this matters for large CSV contexts.

---

## Step 7 — Partition Loop

Explain full loop:

for each partition:

1 compute concepts
2 save
3 clear memory

Show how this loop handles arbitrary numbers of partitions (depending on |M|) and therefore arbitrary context sizes.

---

## Step 8 — Partition Reassembly

Explain:

* loading all partitions
* removing duplicates
* sorting concepts

Explain complexity and memory footprint, and how to keep it manageable even when there are many concepts.

---

## Step 9 — Lattice Edges

Explain how to compute cover relation:

Concept A -> Concept B if:

intent(A) ⊂ intent(B)

and no intermediate concept exists.

Explain algorithm and complexity.

For **small contexts**, the resulting cover relation must be equivalent to the one produced by FCA4J (same Hasse diagram structure).

---

## Step 10 — DOT Generation

Explain:

* node numbering
* formatting identical to the Animals11.dot example

Explain writing algorithm.

Clarify how the algorithm produces consistent, deterministic DOT output so that, for small trellises, the result can be directly compared to FCA4J.

---

# CODE REQUIREMENTS

The final code must be:

* clean Python
* modular
* commented
* deterministic

Functions required:

load_context()

closure()

next_closure_partition()

save_partition()

load_partitions()

compute_edges()

write_dot()

main()

You may introduce helper functions or classes if this helps maintain clarity and modularity.

---

# PERFORMANCE REQUIREMENTS

The algorithm must:

* handle contexts larger than RAM
* avoid storing all concepts simultaneously
* release memory after each partition
* scale with the number of attributes and objects, without assuming any fixed size

---

# CORRECTNESS AND VALIDATION REQUIREMENTS

* For **small contexts** (such as Animals11 and similar test contexts), the lattice (set of concepts with their intents and extents, and the cover relation) must be **identical in structure** to the lattice computed by FCA4J.
* The DOT files produced for such small contexts must be comparable to FCA4J's DOT export (Animals11.dot), differing only in inessential details like node identifiers or ordering if necessary.
* You must keep this equivalence with FCA4J in mind when designing both the enumeration and edge-computation algorithms.

---

# FINAL OUTPUT

Output:

1 Detailed reasoning (following all steps above)
2 Complete Python code
3 Example execution:

python lattice.py Animals11.csv

Output:

Lattice/Animals11_LLM.dot

---

Think carefully and reason step-by-step before writing the final code. The algorithm must work for CSV contexts of **any size**, and for small trellises its results must match those obtained with **FCA4J**.