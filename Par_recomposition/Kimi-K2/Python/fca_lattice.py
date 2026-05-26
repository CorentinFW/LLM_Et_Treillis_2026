#!/usr/bin/env python3
"""
FCA Lattice Computation System
================================
Memory-efficient formal concept analysis with block-wise processing,
incremental persistence, and deterministic DOT generation.

Compliant with the FCA4J-like DOT output specification.

python3 fca_lattice.py input.csv output.dot
python3 fca_lattice.py input.csv output.dot --ram-budget 256
python3 fca_lattice.py input.csv output.dot --max-block-objects 1000
"""

import csv
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Iterator, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import heapq


# =============================================================================
# SECTION 1: Utility Functions
# =============================================================================

def lectic_less(a: int, b: int) -> bool:
    """
    Return True if a < b in lectic order.

    Lectic order: A < B iff the smallest element in the symmetric difference
    A △ B belongs to B.

    For bitsets where bit i represents attribute i (0-indexed, i=0 is smallest):
    - Compute diff = a ^ b
    - Find smallest set bit in diff: diff & -diff
    - If that bit is set in b, then a < b.
    """
    if a == b:
        return False
    diff = a ^ b
    smallest_diff = diff & -diff
    return (b & smallest_diff) != 0


def lectic_greater(a: int, b: int) -> bool:
    """Return True if a > b in lectic order."""
    return lectic_less(b, a)


def popcount(x: int) -> int:
    """Return the number of set bits in x."""
    return x.bit_count()


def intent_to_tuple(intent_bits: int) -> Tuple[int, ...]:
    """Convert an intent bitset to a sorted tuple of attribute indices."""
    result = []
    idx = 0
    bits = intent_bits
    while bits:
        if bits & 1:
            result.append(idx)
        bits >>= 1
        idx += 1
    return tuple(result)


def escape_dot_label(text: str) -> str:
    """
    Escape special characters in DOT record label text.
    Characters escaped: backslash, double quote, braces, pipe, angle brackets.
    """
    return (text
            .replace("\\", "\\\\")  # escape backslash first
            .replace('"', '\"')
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("|", r"\|")
            .replace("<", r"\<")
            .replace(">", r"\>"))


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    import hashlib
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# =============================================================================
# SECTION 2: CSV Parser and Validator
# =============================================================================

@dataclass
class ParsedContext:
    """Result of parsing a valid FCA CSV file."""
    objects: List[str]
    attributes: List[str]
    object_bitsets: List[int]  # Each int is an attribute bitset for one object
    delimiter: str


class CSVParser:
    """
    Robust CSV parser for binary formal contexts.

    Validates:
    - Constant column count
    - Binary values (0/1) in columns 2..N
    - Non-empty header and data
    - Empty first header cell
    """

    @staticmethod
    def detect_delimiter(first_line: str) -> str:
        """Auto-detect between comma and semicolon."""
        comma_count = first_line.count(",")
        semicolon_count = first_line.count(";")
        return ";" if semicolon_count > comma_count else ","

    @staticmethod
    def normalize_cell(cell: str) -> str:
        """Trim whitespace and strip external quotes."""
        cell = cell.strip()
        if len(cell) >= 2 and cell.startswith('"') and cell.endswith('"'):
            cell = cell[1:-1]
        return cell.strip()

    def parse(self, filepath: Path) -> ParsedContext:
        """Parse and validate a CSV file."""
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            first_line = f.readline()
            f.seek(0)

            delimiter = self.detect_delimiter(first_line)
            reader = csv.reader(f, delimiter=delimiter)

            rows = list(reader)

        if len(rows) < 2:
            raise ValueError("CSV must have at least one header row and one data row")

        header = rows[0]
        expected_cols = len(header)

        if expected_cols < 2:
            raise ValueError("CSV must have at least one object column and one attribute column")

        # Validate first header cell is empty
        first_header = self.normalize_cell(header[0])
        if first_header != "":
            raise ValueError(f"First header cell must be empty, got: '{first_header}'")

        attributes = [self.normalize_cell(h) for h in header[1:]]
        m = len(attributes)

        objects = []
        object_bitsets = []

        for row_idx, row in enumerate(rows[1:], start=2):
            if len(row) != expected_cols:
                raise ValueError(
                    f"Row {row_idx}: expected {expected_cols} columns, got {len(row)}"
                )

            obj_name = self.normalize_cell(row[0])
            objects.append(obj_name)

            bits = 0
            for j, cell in enumerate(row[1:], start=0):
                val = self.normalize_cell(cell)
                if val not in ("0", "1"):
                    raise ValueError(
                        f"Row {row_idx}, col {j+2}: non-binary value '{val}'"
                    )
                if val == "1":
                    bits |= (1 << j)

            object_bitsets.append(bits)

        if len(objects) == 0:
            raise ValueError("No data rows found")

        return ParsedContext(
            objects=objects,
            attributes=attributes,
            object_bitsets=object_bitsets,
            delimiter=delimiter
        )


# =============================================================================
# SECTION 3: Block Partitioner
# =============================================================================

@dataclass
class BlockInfo:
    """Information about a single block."""
    block_id: int
    filepath: Path
    start_idx: int  # Global object index of first object in block
    end_idx: int    # Global object index of last object in block (exclusive)
    size: int


class BlockPartitioner:
    """
    Partitions the object set into horizontal blocks sized to fit in RAM.
    """

    def __init__(self, work_dir: Path, max_block_objects: Optional[int] = None):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.max_block_objects = max_block_objects

    def compute_block_size(self, m: int, ram_budget_mb: int = 512) -> int:
        """
        Compute optimal block size based on attribute count and RAM budget.

        Each object requires:
        - ~m/8 bytes for the bitset (in Python int, actual overhead is higher)
        - Additional overhead for Python objects and temporary structures

        We use a safety factor of 8 to account for Python overhead.
        """
        if self.max_block_objects is not None:
            return self.max_block_objects

        bytes_per_object = max(8, (m // 8) + 8)  # bitset + overhead
        safety_factor = 8
        budget_bytes = ram_budget_mb * 1024 * 1024
        block_size = budget_bytes // (bytes_per_object * safety_factor)
        return max(1, min(block_size, 1_000_000))

    def partition(self, parsed: ParsedContext) -> List[BlockInfo]:
        """Partition objects into blocks and write block files."""
        n = len(parsed.objects)
        m = len(parsed.attributes)
        block_size = self.compute_block_size(m)

        blocks = []
        block_id = 0

        for start in range(0, n, block_size):
            end = min(start + block_size, n)
            block_objects = parsed.objects[start:end]
            block_bitsets = parsed.object_bitsets[start:end]

            block_path = self.work_dir / f"block_{block_id}.csv"

            with open(block_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=parsed.delimiter)
                # Header
                header = [""] + parsed.attributes
                writer.writerow(header)
                # Data rows
                for obj_name, bits in zip(block_objects, block_bitsets):
                    row = [obj_name]
                    for j in range(m):
                        row.append("1" if (bits >> j) & 1 else "0")
                    writer.writerow(row)

            blocks.append(BlockInfo(
                block_id=block_id,
                filepath=block_path,
                start_idx=start,
                end_idx=end,
                size=end - start
            ))

            block_id += 1

        return blocks


# =============================================================================
# SECTION 4: NextClosure Enumerator
# =============================================================================

class NextClosure:
    """
    NextClosure algorithm for enumerating all closed intents of a formal context.

    Uses lectic order with the smallest-attribute-differing definition.
    """

    def __init__(self, object_bitsets: List[int], m: int):
        """
        Args:
            object_bitsets: List of attribute bitsets, one per object in the block.
            m: Number of attributes.
        """
        self.object_bitsets = object_bitsets
        self.m = m
        self.n = len(object_bitsets)
        self.all_attrs_mask = (1 << m) - 1
        self.all_objs_mask = (1 << self.n) - 1

        # Precompute attribute-to-object masks for fast extent computation
        # attr_obj_masks[a] = bitset of objects that have attribute a
        self.attr_obj_masks = []
        for a in range(m):
            mask = 0
            for o in range(self.n):
                if (object_bitsets[o] >> a) & 1:
                    mask |= (1 << o)
            self.attr_obj_masks.append(mask)

    def closure(self, intent: int) -> int:
        """
        Compute the intent closure Y'' for the local block.

        Returns the set of attributes shared by all objects that have all
        attributes in the given intent.
        """
        if intent == 0:
            extent_mask = self.all_objs_mask
        else:
            extent_mask = self.all_objs_mask
            y = intent
            a = 0
            while y:
                if y & 1:
                    extent_mask &= self.attr_obj_masks[a]
                    if extent_mask == 0:
                        break
                y >>= 1
                a += 1

        if extent_mask == 0:
            # Empty extent: all attributes are shared (vacuously)
            return self.all_attrs_mask

        # Compute AND of object bitsets for objects in extent
        result = self.all_attrs_mask
        temp = extent_mask
        while temp:
            lsb = temp & -temp
            obj_idx = lsb.bit_length() - 1
            result &= self.object_bitsets[obj_idx]
            temp ^= lsb

        return result

    def enumerate(self) -> Iterator[int]:
        """
        Generate all closed intents in lectic order using NextClosure.

        Yields intent bitsets.
        """
        Y = self.closure(0)
        yield Y

        while True:
            Y_next = None
            # Try attributes from largest to smallest
            for i in range(self.m - 1, -1, -1):
                if not ((Y >> i) & 1):  # attribute i not in Y
                    # Y ⊕ i = (Y with bits >= i cleared) | (1 << i)
                    Y_candidate = (Y & ((1 << i) - 1)) | (1 << i)
                    Y_closed = self.closure(Y_candidate)
                    if lectic_greater(Y_closed, Y):
                        Y_next = Y_closed
                        break

            if Y_next is None:
                break

            Y = Y_next
            yield Y


# =============================================================================
# SECTION 5: Concept Merge and Deduplication
# =============================================================================

@dataclass
class Concept:
    """A formal concept with global intent and extent."""
    id: int
    intent_bits: int
    extent_bits: int
    intent_size: int
    extent_size: int


class ConceptMerge:
    """
    Merges candidate concepts from multiple blocks, deduplicates by intent,
    intersects extents, and verifies global closure.
    """

    def __init__(self, work_dir: Path, n_objects: int, m_attributes: int,
                 global_obj_masks: Optional[List[int]] = None):
        self.work_dir = work_dir
        self.n = n_objects
        self.m = m_attributes
        self.global_obj_masks = global_obj_masks
        self.all_attrs_mask = (1 << m_attributes) - 1

    def _local_to_global_extent(self, local_extent: int, block_start: int) -> int:
        """Convert a local extent bitset to global object indices."""
        if local_extent == 0:
            return 0

        global_extent = 0
        temp = local_extent
        while temp:
            lsb = temp & -temp
            local_idx = lsb.bit_length() - 1
            global_extent |= (1 << (block_start + local_idx))
            temp ^= lsb
        return global_extent

    def _verify_global_closure(self, intent: int, extent: int) -> bool:
        """
        Verify that intent == (extent)' globally.

        Uses global_obj_masks if available (O(m)), otherwise falls back to
        a slower method.
        """
        if self.global_obj_masks is not None:
            # Compute (extent)' using precomputed masks
            # Attribute a is in (extent)' iff all objects in extent have a
            # i.e., (extent & ~global_obj_masks[a]) == 0
            computed_intent = 0
            for a in range(self.m):
                mask = self.global_obj_masks[a]
                if (extent & ~mask) == 0:
                    computed_intent |= (1 << a)
            return computed_intent == intent
        else:
            # Fallback: not implemented in this version
            raise NotImplementedError("Global closure verification requires global_obj_masks")

    def merge(self, candidate_files: List[Path], blocks: List[BlockInfo]) -> Path:
        """
        Merge candidate files from all blocks, deduplicate, verify closure.

        Returns path to global_concepts.jsonl.
        """
        # Step 1: Sort each candidate file by intent_bits
        sorted_files = []
        for cand_file in candidate_files:
            sorted_file = self._sort_candidate_file(cand_file)
            sorted_files.append(sorted_file)

        # Step 2: K-way merge to group by intent and intersect extents
        merged_file = self.work_dir / "merged_candidates.jsonl"
        self._kway_merge(sorted_files, blocks, merged_file)

        # Step 3: Verify global closure and collect valid concepts
        valid_concepts = []
        with open(merged_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                intent_bits, extent_bits = map(int, line.split(","))
                if self._verify_global_closure(intent_bits, extent_bits):
                    valid_concepts.append((intent_bits, extent_bits))

        # Step 4: Deterministic sorting and ID assignment
        # Sort by: intent size descending, then lexicographic tuple ascending
        valid_concepts.sort(key=lambda x: (-popcount(x[0]), intent_to_tuple(x[0])))

        global_concepts_file = self.work_dir / "global_concepts.jsonl"
        with open(global_concepts_file, "w", encoding="utf-8") as f:
            for idx, (intent_bits, extent_bits) in enumerate(valid_concepts):
                concept = {
                    "id": idx,
                    "intent_bits": intent_bits,
                    "extent_bits": extent_bits,
                    "intent_size": popcount(intent_bits),
                    "extent_size": popcount(extent_bits)
                }
                f.write(json.dumps(concept) + "\n")

        return global_concepts_file

    def _sort_candidate_file(self, cand_file: Path) -> Path:
        """Sort a candidate file by intent_bits and return the sorted file path."""
        records = []
        with open(cand_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    intent_bits, extent_bits = map(int, line.split(","))
                    records.append((intent_bits, extent_bits))

        records.sort(key=lambda x: x[0])

        sorted_file = cand_file.with_suffix(".sorted.jsonl")
        with open(sorted_file, "w", encoding="utf-8") as f:
            for intent_bits, extent_bits in records:
                f.write(f"{intent_bits},{extent_bits}\n")

        return sorted_file

    def _kway_merge(self, sorted_files: List[Path], blocks: List[BlockInfo],
                    output_file: Path):
        """
        Perform k-way merge of sorted candidate files.

        Groups records by intent_bits and intersects extent_bits across blocks.
        """
        readers = []
        heap = []

        try:
            for i, sf in enumerate(sorted_files):
                r = open(sf, "r", encoding="utf-8")
                readers.append(r)
                line = r.readline()
                if line.strip():
                    intent_bits, extent_bits = map(int, line.strip().split(","))
                    heapq.heappush(heap, (intent_bits, extent_bits, i))

            with open(output_file, "w", encoding="utf-8") as out:
                current_intent = None
                current_extent = (1 << self.n) - 1  # All objects

                while heap:
                    intent_bits, extent_bits, file_idx = heapq.heappop(heap)
                    block_start = blocks[file_idx].start_idx
                    global_extent = self._local_to_global_extent(extent_bits, block_start)

                    if intent_bits != current_intent:
                        if current_intent is not None:
                            out.write(f"{current_intent},{current_extent}\n")
                        current_intent = intent_bits
                        current_extent = global_extent
                    else:
                        current_extent &= global_extent

                    # Read next from same file
                    line = readers[file_idx].readline()
                    if line.strip():
                        next_intent, next_extent = map(int, line.strip().split(","))
                        heapq.heappush(heap, (next_intent, next_extent, file_idx))

                # Write last group
                if current_intent is not None:
                    out.write(f"{current_intent},{current_extent}\n")

        finally:
            for r in readers:
                r.close()


# =============================================================================
# SECTION 6: Cover Relation Computation
# =============================================================================

class CoverBuilder:
    """
    Computes the cover relation of the concept lattice.

    Uses the key insight: in the intent poset, c covers d iff
    intent(d) ⊂ intent(c) and |intent(c)| = |intent(d)| + 1.
    """

    def __init__(self, work_dir: Path, m_attributes: int):
        self.work_dir = work_dir
        self.m = m_attributes

    def compute_covers(self, global_concepts_file: Path) -> Path:
        """
        Compute cover edges and write to edges.jsonl.

        Uses a correct cover detection that does not assume intent sizes
        differ by exactly 1 (which fails when intermediate size buckets are empty).

        For each concept c, its upper covers are the minimal concepts (w.r.t.
        intent inclusion) among all concepts with strictly larger intents.

        Returns path to edges file.
        """
        # Step 1: Read all concepts
        concepts = []
        with open(global_concepts_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                concept = json.loads(line)
                concepts.append((concept["id"], concept["intent_bits"], concept["intent_size"]))

        # Step 2: Bucket by intent size for efficient lookup
        buckets: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        for cid, intent, size in concepts:
            buckets[size].append((cid, intent))

        # Step 3: Build a set of all intent bitsets for fast membership testing
        intent_set = {intent for _, intent, _ in concepts}

        # Step 4: Compute edges
        edges = []

        for lower_id, lower_intent, lower_size in concepts:
            covers = []  # List of (cover_id, cover_intent)

            # Check all concepts with larger intent sizes, in increasing order
            max_size = max(buckets.keys()) if buckets else 0
            for upper_size in range(lower_size + 1, max_size + 1):
                for upper_id, upper_intent in buckets.get(upper_size, []):
                    # Check if lower_intent is a strict subset of upper_intent
                    if lower_intent != upper_intent and (lower_intent & upper_intent) == lower_intent:
                        # Check if upper is blocked by an existing cover
                        # (i.e., there exists a cover e with lower ⊂ e ⊂ upper)
                        blocked = False
                        for cover_id, cover_intent in covers:
                            if (cover_intent & upper_intent) == cover_intent and cover_intent != upper_intent:
                                blocked = True
                                break
                        if not blocked:
                            covers.append((upper_id, upper_intent))

            for cover_id, _ in covers:
                edges.append((lower_id, cover_id))

        # Sort edges deterministically
        edges.sort()

        edges_file = self.work_dir / "edges.jsonl"
        with open(edges_file, "w", encoding="utf-8") as f:
            for src, tgt in edges:
                f.write(json.dumps({"src": src, "tgt": tgt}) + "\n")

        return edges_file


# =============================================================================
# SECTION 7: DOT Generator
# =============================================================================

class DOTGenerator:
    """
    Generates Graphviz DOT output compliant with the FCA4J specification.
    """

    def __init__(self, attributes: List[str], objects: List[str]):
        self.attributes = attributes
        self.objects = objects
        self.m = len(attributes)
        self.n = len(objects)

    def _intent_names(self, intent_bits: int) -> List[str]:
        """Get sorted attribute names for an intent bitset."""
        names = []
        bits = intent_bits
        idx = 0
        while bits:
            if bits & 1:
                names.append(self.attributes[idx])
            bits >>= 1
            idx += 1
        return sorted(names)

    def _extent_names(self, extent_bits: int) -> List[str]:
        """Get sorted object names for an extent bitset."""
        names = []
        bits = extent_bits
        idx = 0
        while bits:
            if bits & 1:
                names.append(self.objects[idx])
            bits >>= 1
            idx += 1
        return sorted(names)

    def generate(self, global_concepts_file: Path, edges_file: Path,
                 output_file: Path):
        """Generate the DOT file."""
        with open(output_file, "w", encoding="utf-8") as out:
            out.write("digraph G {\n")
            out.write("    rankdir=BT;\n")

            # Write nodes
            with open(global_concepts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    concept = json.loads(line)
                    cid = concept["id"]
                    intent_bits = concept["intent_bits"]
                    extent_bits = concept["extent_bits"]
                    i_size = concept["intent_size"]
                    e_size = concept["extent_size"]

                    intent_names = self._intent_names(intent_bits)
                    extent_names = self._extent_names(extent_bits)

                    intent_text = r"\n".join(escape_dot_label(name) for name in intent_names)
                    extent_text = r"\n".join(escape_dot_label(name) for name in extent_names)

                    # Color assignment
                    if e_size == 0:
                        color_attrs = "style=filled,fillcolor=lightblue,"
                    elif e_size == 1:
                        color_attrs = ""
                    else:  # e_size > 1
                        color_attrs = "style=filled,fillcolor=orange,"

                    label = f"{{<{cid}> (I: {i_size}, E: {e_size})|{intent_text}|{extent_text}}}"
                    out.write(f'    {cid} [shape=record,{color_attrs}label="{label}"];\n')

            # Write edges
            with open(edges_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    edge = json.loads(line)
                    out.write(f'    {edge["src"]} -> {edge["tgt"]};\n')

            out.write("}\n")


# =============================================================================
# SECTION 8: Manifest and Pipeline Orchestration
# =============================================================================

@dataclass
class Manifest:
    """Tracks pipeline execution state."""
    input_file: str
    stage: str = "INIT"
    completed_blocks: List[int] = field(default_factory=list)
    attribute_count: int = 0
    object_count: int = 0
    block_count: int = 0

    def to_file(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "input_file": self.input_file,
                "stage": self.stage,
                "completed_blocks": self.completed_blocks,
                "attribute_count": self.attribute_count,
                "object_count": self.object_count,
                "block_count": self.block_count
            }, f, indent=2)

    @classmethod
    def from_file(cls, path: Path) -> "Manifest":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


class LatticeBuilder:
    """
    Main orchestrator for the FCA lattice computation pipeline.
    """

    def __init__(self, work_dir: Optional[Path] = None,
                 ram_budget_mb: int = 512,
                 max_block_objects: Optional[int] = None):
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="fca_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.ram_budget_mb = ram_budget_mb
        self.max_block_objects = max_block_objects
        self.manifest_path = self.work_dir / "manifest.json"

    def build(self, input_csv: Path, output_dot: Path):
        """
        Execute the full pipeline: CSV -> DOT.
        """
        print(f"[FCA] Starting lattice computation")
        print(f"[FCA] Input: {input_csv}")
        print(f"[FCA] Output: {output_dot}")
        print(f"[FCA] Work directory: {self.work_dir}")

        # Stage 0: Parse and partition
        print("[FCA] Stage 0: Parsing CSV and partitioning...")
        parser = CSVParser()
        parsed = parser.parse(input_csv)
        print(f"[FCA]   Objects: {len(parsed.objects)}, Attributes: {len(parsed.attributes)}")

        # Compute global object masks for fast closure verification
        n = len(parsed.objects)
        m = len(parsed.attributes)
        global_obj_masks = []
        for a in range(m):
            mask = 0
            for o in range(n):
                if (parsed.object_bitsets[o] >> a) & 1:
                    mask |= (1 << o)
            global_obj_masks.append(mask)

        # Partition into blocks
        partitioner = BlockPartitioner(
            self.work_dir / "blocks",
            max_block_objects=self.max_block_objects
        )
        blocks = partitioner.partition(parsed)
        print(f"[FCA]   Partitioned into {len(blocks)} blocks")

        # Stage 1: Enumerate local concepts per block
        print("[FCA] Stage 1: Local concept enumeration...")
        candidate_files = []

        for block in blocks:
            print(f"[FCA]   Processing block {block.block_id} ({block.size} objects)...")

            # Load block
            block_parser = CSVParser()
            block_parsed = block_parser.parse(block.filepath)

            # Enumerate concepts
            enumerator = NextClosure(block_parsed.object_bitsets, m)
            candidates = list(enumerator.enumerate())

            # Write candidates: intent_bits,extent_bits_local
            cand_file = self.work_dir / f"candidates_block_{block.block_id}.jsonl"
            with open(cand_file, "w", encoding="utf-8") as f:
                for intent_bits in candidates:
                    # Compute local extent for this intent
                    extent_mask = (1 << block.size) - 1
                    y = intent_bits
                    a = 0
                    while y:
                        if y & 1:
                            # Find objects in block with attribute a
                            attr_mask = 0
                            for o in range(block.size):
                                if (block_parsed.object_bitsets[o] >> a) & 1:
                                    attr_mask |= (1 << o)
                            extent_mask &= attr_mask
                            if extent_mask == 0:
                                break
                        y >>= 1
                        a += 1

                    f.write(f"{intent_bits},{extent_mask}\n")

            candidate_files.append(cand_file)

        # Stage 2: Merge and deduplicate
        print("[FCA] Stage 2: Merging and deduplicating...")
        merger = ConceptMerge(
            self.work_dir, n, m,
            global_obj_masks=global_obj_masks
        )
        global_concepts_file = merger.merge(candidate_files, blocks)

        # Count concepts
        concept_count = 0
        with open(global_concepts_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    concept_count += 1
        print(f"[FCA]   Found {concept_count} global concepts")

        # Stage 3: Compute covers
        print("[FCA] Stage 3: Computing cover relations...")
        cover_builder = CoverBuilder(self.work_dir, m)
        edges_file = cover_builder.compute_covers(global_concepts_file)

        edge_count = 0
        with open(edges_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    edge_count += 1
        print(f"[FCA]   Found {edge_count} cover edges")

        # Stage 4: Generate DOT
        print("[FCA] Stage 4: Generating DOT...")
        dot_gen = DOTGenerator(parsed.attributes, parsed.objects)
        dot_gen.generate(global_concepts_file, edges_file, output_dot)

        print(f"[FCA] Done. Output written to {output_dot}")
        return output_dot


# =============================================================================
# SECTION 9: Main Entry Point
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute FCA lattice from binary CSV context and emit DOT."
    )
    parser.add_argument("input", type=Path, help="Input CSV file")
    parser.add_argument("output", type=Path, help="Output DOT file")
    parser.add_argument("--work-dir", type=Path, default=None,
                        help="Working directory for intermediate files")
    parser.add_argument("--ram-budget", type=int, default=512,
                        help="RAM budget in MB (default: 512)")
    parser.add_argument("--max-block-objects", type=int, default=None,
                        help="Maximum objects per block (overrides RAM budget)")

    args = parser.parse_args()

    builder = LatticeBuilder(
        work_dir=args.work_dir,
        ram_budget_mb=args.ram_budget,
        max_block_objects=args.max_block_objects
    )

    builder.build(args.input, args.output)


if __name__ == "__main__":
    main()
