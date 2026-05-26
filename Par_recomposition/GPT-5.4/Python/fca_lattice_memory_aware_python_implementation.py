from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple


# ============================================================
# Exceptions
# ============================================================


class FCAError(Exception):
    pass


class CSVValidationError(FCAError):
    pass


class PartitionCorruptionError(FCAError):
    pass


# ============================================================
# Formal Context
# ============================================================


@dataclass(frozen=True)
class FormalContext:
    objects: Tuple[str, ...]
    attributes: Tuple[str, ...]
    object_intents: Tuple[int, ...]
    attribute_extents: Tuple[int, ...]

    @property
    def object_count(self) -> int:
        return len(self.objects)

    @property
    def attribute_count(self) -> int:
        return len(self.attributes)


# ============================================================
# Concept Model
# ============================================================


@dataclass(frozen=True)
class Concept:
    intent: int
    extent: int
    intent_size: int
    extent_size: int

    @property
    def canonical_id(self) -> str:
        return hashlib.sha256(str(self.intent).encode()).hexdigest()


# ============================================================
# Bitset Utilities
# ============================================================


class BitsetUtils:
    @staticmethod
    def bit_count(x: int) -> int:
        return x.bit_count()

    @staticmethod
    def contains(a: int, b: int) -> bool:
        return (a & b) == b

    @staticmethod
    def iter_bits(x: int) -> Iterator[int]:
        index = 0
        while x:
            if x & 1:
                yield index
            x >>= 1
            index += 1

    @staticmethod
    def to_names(bitset: int, names: Tuple[str, ...]) -> List[str]:
        return [names[i] for i in BitsetUtils.iter_bits(bitset)]


# ============================================================
# CSV Parser
# ============================================================


class ContextCSVParser:
    VALID_VALUES = {"0", "1"}

    @staticmethod
    def parse(path: str | Path) -> FormalContext:
        path = Path(path)

        if not path.exists():
            raise CSVValidationError(f"Missing CSV file: {path}")

        raw = path.read_text(encoding="utf-8")

        if not raw.strip():
            raise CSVValidationError("CSV file is empty")

        delimiter = ContextCSVParser._detect_delimiter(raw)

        with open(path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            rows = list(reader)

        if len(rows) < 2:
            raise CSVValidationError("CSV must contain at least one header and one data row")

        header = [cell.strip() for cell in rows[0]]

        if len(header) < 2:
            raise CSVValidationError("CSV must contain at least one attribute")

        attributes = tuple(header[1:])
        expected_width = len(header)

        objects: List[str] = []
        object_intents: List[int] = []

        for row_index, row in enumerate(rows[1:], start=2):
            if len(row) != expected_width:
                raise CSVValidationError(
                    f"Row {row_index} has invalid width: {len(row)} != {expected_width}"
                )

            object_name = row[0].strip()
            values = [v.strip() for v in row[1:]]

            for value in values:
                if value not in ContextCSVParser.VALID_VALUES:
                    raise CSVValidationError(
                        f"Invalid binary value '{value}' at row {row_index}"
                    )

            intent = 0
            for i, value in enumerate(values):
                if value == "1":
                    intent |= 1 << i

            objects.append(object_name)
            object_intents.append(intent)

        attribute_extents = [0 for _ in attributes]

        for object_index, intent in enumerate(object_intents):
            for attribute_index in BitsetUtils.iter_bits(intent):
                attribute_extents[attribute_index] |= 1 << object_index

        return FormalContext(
            objects=tuple(objects),
            attributes=tuple(attributes),
            object_intents=tuple(object_intents),
            attribute_extents=tuple(attribute_extents),
        )

    @staticmethod
    def _detect_delimiter(raw: str) -> str:
        comma_count = raw.count(",")
        semicolon_count = raw.count(";")

        if semicolon_count > comma_count:
            return ";"

        return ","


# ============================================================
# Closure Engine
# ============================================================


class ClosureEngine:
    def __init__(self, context: FormalContext):
        self.context = context
        self.full_extent = (1 << context.object_count) - 1
        self.full_intent = (1 << context.attribute_count) - 1

    def extent_from_intent(self, intent: int) -> int:
        extent = self.full_extent

        for attribute_index in BitsetUtils.iter_bits(intent):
            extent &= self.context.attribute_extents[attribute_index]

        return extent

    def intent_from_extent(self, extent: int) -> int:
        intent = self.full_intent

        for object_index in BitsetUtils.iter_bits(extent):
            intent &= self.context.object_intents[object_index]

        return intent

    def closure(self, intent: int) -> Tuple[int, int]:
        extent = self.extent_from_intent(intent)
        closed_intent = self.intent_from_extent(extent)
        return closed_intent, extent


# ============================================================
# Partition Storage
# ============================================================


class PartitionStorage:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def create_partition(self, name: str) -> Path:
        return self.directory / f"{name}.sqlite"

    def initialize_partition(self, path: Path) -> None:
        connection = sqlite3.connect(path)

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS concepts (
                    canonical_id TEXT PRIMARY KEY,
                    intent INTEGER NOT NULL,
                    extent INTEGER NOT NULL,
                    intent_size INTEGER NOT NULL,
                    extent_size INTEGER NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            connection.commit()

        finally:
            connection.close()

    def append_concept(self, path: Path, concept: Concept) -> None:
        connection = sqlite3.connect(path)

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO concepts (
                    canonical_id,
                    intent,
                    extent,
                    intent_size,
                    extent_size
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    concept.canonical_id,
                    str(concept.intent),
                    str(concept.extent),
                    concept.intent_size,
                    concept.extent_size,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def stream_concepts(self, path: Path) -> Iterator[Concept]:
        connection = sqlite3.connect(path)

        try:
            cursor = connection.cursor()

            rows = cursor.execute(
                """
                SELECT intent, extent, intent_size, extent_size
                FROM concepts
                ORDER BY intent_size ASC, intent ASC
                """
            )

            for row in rows:
                yield Concept(
                    intent=int(row[0]),
                    extent=int(row[1]),
                    intent_size=int(row[2]),
                    extent_size=int(row[3]),
                )

        finally:
            connection.close()


# ============================================================
# NextClosure Enumeration
# ============================================================


class NextClosureEnumerator:
    def __init__(self, context: FormalContext, closure_engine: ClosureEngine):
        self.context = context
        self.closure_engine = closure_engine
        self.attribute_count = context.attribute_count

    def enumerate_concepts(self) -> Iterator[Concept]:
        current, extent = self.closure_engine.closure(0)

        while True:
            yield Concept(
                intent=current,
                extent=extent,
                intent_size=BitsetUtils.bit_count(current),
                extent_size=BitsetUtils.bit_count(extent),
            )

            next_intent = self._next_closure(current)

            if next_intent is None:
                break

            current, extent = self.closure_engine.closure(next_intent)

    def _next_closure(self, current: int) -> Optional[int]:
        for i in reversed(range(self.attribute_count)):
            if not ((current >> i) & 1):
                candidate = current | (1 << i)

                for j in range(i):
                    if (current >> j) & 1:
                        candidate |= 1 << j
                    else:
                        candidate &= ~(1 << j)

                closure, _ = self.closure_engine.closure(candidate)

                if self._lectic_less(current, closure, i):
                    return closure

        return None

    @staticmethod
    def _lectic_less(a: int, b: int, pivot: int) -> bool:
        if ((b >> pivot) & 1) == 0:
            return False

        for i in range(pivot):
            if ((a >> i) & 1) != ((b >> i) & 1):
                return False

        return True


# ============================================================
# Merge and Deduplication
# ============================================================


class ConceptMerger:
    def __init__(self):
        self.concepts: Dict[str, Concept] = {}

    def merge_partition(self, concepts: Iterable[Concept]) -> None:
        for concept in concepts:
            existing = self.concepts.get(concept.canonical_id)

            if existing is None:
                self.concepts[concept.canonical_id] = concept
                continue

            if existing.intent != concept.intent:
                raise FCAError("Hash collision detected")

    def ordered_concepts(self) -> List[Concept]:
        return sorted(
            self.concepts.values(),
            key=lambda c: (c.intent_size, c.intent),
        )


# ============================================================
# Cover Relation Computation
# ============================================================


class CoverRelationComputer:
    def __init__(self, concepts: List[Concept]):
        self.concepts = concepts

    def compute(self) -> List[Tuple[int, int]]:
        edges: List[Tuple[int, int]] = []

        concepts_by_size: Dict[int, List[int]] = {}

        for index, concept in enumerate(self.concepts):
            concepts_by_size.setdefault(concept.intent_size, []).append(index)

        for lower_index, lower in enumerate(self.concepts):
            candidates: List[int] = []

            for size in range(lower.intent_size + 1, self._max_size() + 1):
                candidates.extend(concepts_by_size.get(size, []))

            minimal_candidates = []

            for upper_index in candidates:
                upper = self.concepts[upper_index]

                if not BitsetUtils.contains(upper.intent, lower.intent):
                    continue

                intermediate_exists = False

                for middle_index in candidates:
                    if middle_index in (lower_index, upper_index):
                        continue

                    middle = self.concepts[middle_index]

                    if (
                        BitsetUtils.contains(middle.intent, lower.intent)
                        and BitsetUtils.contains(upper.intent, middle.intent)
                        and middle.intent != lower.intent
                        and middle.intent != upper.intent
                    ):
                        intermediate_exists = True
                        break

                if not intermediate_exists:
                    minimal_candidates.append(upper_index)

            for upper_index in minimal_candidates:
                edges.append((lower_index, upper_index))

        return sorted(edges)

    def _max_size(self) -> int:
        return max(c.intent_size for c in self.concepts)


# ============================================================
# DOT Generation
# ============================================================


class DOTGenerator:
    def __init__(self, context: FormalContext):
        self.context = context

    def generate(
        self,
        concepts: List[Concept],
        edges: List[Tuple[int, int]],
        output_path: str | Path,
    ) -> None:
        output_path = Path(output_path)

        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("digraph G {\n")
            handle.write("    rankdir=BT;\n")

            for node_id, concept in enumerate(concepts):
                handle.write(self._format_node(node_id, concept))

            for source, target in edges:
                handle.write(f"    {source} -> {target};\n")

            handle.write("}\n")

    def _format_node(self, node_id: int, concept: Concept) -> str:
        intent_names = BitsetUtils.to_names(
            concept.intent,
            self.context.attributes,
        )

        extent_names = BitsetUtils.to_names(
            concept.extent,
            self.context.objects,
        )

        intent_text = "\\n".join(self._escape(x) for x in intent_names)
        extent_text = "\\n".join(self._escape(x) for x in extent_names)

        metadata = (
            f"{node_id} "
            f"(I: {concept.intent_size}, E: {concept.extent_size})"
        )

        label = (
            "{"
            f"{metadata}|{intent_text}|{extent_text}"
            "}"
        )

        fillcolor = self._fillcolor(concept.extent_size)

        if fillcolor:
            return (
                f'    {node_id} '
                f'[shape=record,style=filled,fillcolor={fillcolor},label="{label}"];\n'
            )

        return (
            f'    {node_id} '
            f'[shape=record,style=filled,label="{label}"];\n'
        )

    @staticmethod
    def _fillcolor(extent_size: int) -> Optional[str]:
        if extent_size == 0:
            return "lightblue"

        if extent_size > 1:
            return "orange"

        return None

    @staticmethod
    def _escape(value: str) -> str:
        return (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )


# ============================================================
# Verification
# ============================================================


class FCAValidator:
    def __init__(self, context: FormalContext, closure_engine: ClosureEngine):
        self.context = context
        self.closure_engine = closure_engine

    def validate_concepts(self, concepts: Iterable[Concept]) -> None:
        seen: Set[int] = set()

        for concept in concepts:
            if concept.intent in seen:
                raise FCAError("Duplicate concept intent detected")

            seen.add(concept.intent)

            closure, extent = self.closure_engine.closure(concept.intent)

            if closure != concept.intent:
                raise FCAError("Intent is not closed")

            if extent != concept.extent:
                raise FCAError("Extent mismatch")


# ============================================================
# Orchestrator
# ============================================================


class FCALatticeSystem:
    def __init__(
        self,
        csv_path: str | Path,
        working_directory: Optional[str | Path] = None,
    ):
        self.csv_path = Path(csv_path)

        if working_directory is None:
            working_directory = tempfile.mkdtemp(prefix="fca_")

        self.working_directory = Path(working_directory)
        self.storage = PartitionStorage(self.working_directory)

    def run(self, dot_output_path: str | Path) -> None:
        context = ContextCSVParser.parse(self.csv_path)

        closure_engine = ClosureEngine(context)

        validator = FCAValidator(context, closure_engine)

        enumerator = NextClosureEnumerator(context, closure_engine)

        partition_path = self.storage.create_partition("partition_0")
        self.storage.initialize_partition(partition_path)

        for concept in enumerator.enumerate_concepts():
            self.storage.append_concept(partition_path, concept)

        streamed_concepts = list(self.storage.stream_concepts(partition_path))

        validator.validate_concepts(streamed_concepts)

        merger = ConceptMerger()
        merger.merge_partition(streamed_concepts)

        ordered_concepts = merger.ordered_concepts()

        edge_computer = CoverRelationComputer(ordered_concepts)
        edges = edge_computer.compute()

        dot_generator = DOTGenerator(context)

        dot_generator.generate(
            ordered_concepts,
            edges,
            dot_output_path,
        )


# ============================================================
# Example CLI
# ============================================================


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory-aware FCA lattice generator")

    parser.add_argument("csv", help="Input formal context CSV")
    parser.add_argument("dot", help="Output DOT file")
    parser.add_argument(
        "--workdir",
        default=None,
        help="Optional working directory",
    )

    args = parser.parse_args()

    system = FCALatticeSystem(
        csv_path=args.csv,
        working_directory=args.workdir,
    )

    system.run(args.dot)

    print(f"DOT lattice generated at: {args.dot}")
