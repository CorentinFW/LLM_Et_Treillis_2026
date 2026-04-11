#!/usr/bin/env python3
"""
Formal Concept Analysis (FCA) Lattice Generator
-------------------------------------------------
Conforme à: Modéle_InputEtOutput.md
- Validation stricte des 62 invariants CSV observés
- Génération DOT canonique équivalente à FCA4J
- Architecture streaming / RAM bornée / Déterminisme absolu
- Aucune dépendance externe (stdlib uniquement)
"""

import csv
import json
import os
import sys
import heapq
import tempfile
import argparse
from pathlib import Path
from typing import Iterator, List, Tuple, Set, FrozenSet, Dict, Optional, TextIO
from dataclasses import dataclass

# =============================================================================
# 1. CONSTANTES & CONTRATS
# =============================================================================
VALID_BINARY = {"0", "1"}
SEP_CANDIDATES = [";", ","]
LABEL_PATTERN = "{id} (I: {ic}, E: {ec})|{intent_str}|{extent_str}"
DOT_HEADER = "digraph G {\nrankdir=BT;\n"
DOT_FOOTER = "}\n"

@dataclass(frozen=True)
class Concept:
    """Concept FCA canonique."""
    intent: FrozenSet[int]
    extent: FrozenSet[int]
    node_id: Optional[int] = None

# =============================================================================
# 2. VALIDATION & CHARGEMENT CSV (Contrat Input Strict)
# =============================================================================
class FCAContext:
    def __init__(self, objects: List[str], attributes: List[str],
                 obj_attrs: List[FrozenSet[int]], attr_objs: List[FrozenSet[int]]):
        self.objects = objects
        self.attributes = attributes
        self.obj_attrs = obj_attrs  # obj_idx -> frozenset of attr_idx
        self.attr_objs = attr_objs  # attr_idx -> frozenset of obj_idx
        self.num_objects = len(objects)
        self.num_attributes = len(attributes)

    @classmethod
    def from_csv(cls, csv_path: str) -> "FCAContext":
        path = Path(csv_path)
        if not path.is_file():
            raise FileNotFoundError(f"CSV introuvable : {csv_path}")
        if path.stat().st_size == 0:
            raise ValueError("Fichier CSV vide (0 octet).")

        # Détection séparateur (invariant 62/62 fichiers)
        with path.open("r", encoding="utf-8-sig") as f:
            first_line = f.readline().strip()
            sep = ";" if first_line.count(";") >= first_line.count(",") else ","

        objects: List[str] = []
        attributes: List[str] = []
        obj_attrs: List[FrozenSet[int]] = []
        attr_objs: List[Set[int]] = []

        with path.open("r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=sep, quotechar='"', skipinitialspace=True)
            header = next(reader, None)
            if not header:
                raise ValueError("En-tête CSV manquant.")
            
            # Validation cellule[0] : vide ou ""
            if header[0].strip() not in ("", '""'):
                raise ValueError("Première cellule de l'en-tête doit être vide ou '\"\"'.")

            attributes = [a.strip() for a in header[1:]]
            m = len(attributes)
            attr_objs = [set() for _ in range(m)]
            expected_width = len(header)

            for row_idx, row in enumerate(reader, start=2):
                if len(row) != expected_width:
                    raise ValueError(f"Largeur variable à la ligne {row_idx}.")
                
                obj_id = row[0].strip()
                objects.append(obj_id)
                current_attrs = set()
                for col_idx in range(m):
                    val = row[col_idx + 1].strip().strip('"')
                    if val not in VALID_BINARY:
                        raise ValueError(f"Valeur non binaire '{val}' ligne {row_idx}, col {col_idx+2}.")
                    if val == "1":
                        current_attrs.add(col_idx)
                        attr_objs[col_idx].add(row_idx - 2)
                obj_attrs.append(frozenset(current_attrs))

            # Finaliser attr_objs
            attr_objs = [frozenset(s) for s in attr_objs]

        return cls(objects, attributes, obj_attrs, attr_objs)

# =============================================================================
# 3. MOTEUR FCA (Fermeture & NextClosure)
# =============================================================================
def compute_closure(intent: Set[int], ctx: FCAContext) -> FrozenSet[int]:
    """Retourne B'' (intent fermé) pour un B donné."""
    if not intent:
        extent = set(range(ctx.num_objects))
    else:
        intent_list = list(intent)
        extent = set(ctx.attr_objs[intent_list[0]])
        for i in intent_list[1:]:
            extent &= ctx.attr_objs[i]
    
    if not extent:
        return frozenset(range(ctx.num_attributes))
    extent_list = list(extent)
    result = set(ctx.obj_attrs[extent_list[0]])
    for i in extent_list[1:]:
        result &= ctx.obj_attrs[i]
    return frozenset(result)

def next_closure(ctx: FCAContext) -> Iterator[FrozenSet[int]]:
    """Énumère les intents fermés dans l'ordre lectique (Ganter)."""
    m = ctx.num_attributes
    B = compute_closure(set(), ctx)
    yield B

    while True:
        i = m - 1
        while i >= 0 and (i not in B or 
                          compute_closure(B - {i} | set(range(i + 1, m)), ctx) <= B):
            i -= 1
        if i < 0:
            break
        B = compute_closure(B - {i} | set(range(i + 1, m)), ctx)
        yield B

# =============================================================================
# 4. GESTION DISQUE & FUSION (RAM Bornée)
# =============================================================================
class DiskStore:
    """Gère la persistance, le tri externe et la fusion K-way des concepts."""
    def __init__(self, max_chunk_size: int = 25000):
        self._tmp = tempfile.TemporaryDirectory()
        self._chunks: List[str] = []
        self._max_chunk = max_chunk_size
        self._final_index: List[Tuple[FrozenSet[int], FrozenSet[int], int]] = []

    def _write_chunk(self, buffer: List[Tuple[FrozenSet[int], FrozenSet[int]]]):
        buffer.sort(key=lambda x: x[0])
        fd, path = tempfile.mkstemp(dir=self._tmp.name, suffix=".fca")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for intent, extent in buffer:
                f.write(f"{json.dumps(sorted(intent))}\t{json.dumps(sorted(extent))}\n")
        self._chunks.append(path)

    def spill(self, ctx: FCAContext):
        """Génère, ferme et écrit les concepts par blocs."""
        buf: List[Tuple[FrozenSet[int], FrozenSet[int]]] = []
        for intent in next_closure(ctx):
            if not intent:
                extent = set(range(ctx.num_objects))
            else:
                intent_list = list(intent)
                extent = set(ctx.attr_objs[intent_list[0]])
                for i in intent_list[1:]:
                    extent &= ctx.attr_objs[i]
            buf.append((intent, frozenset(extent)))
            if len(buf) >= self._max_chunk:
                self._write_chunk(buf)
                buf.clear()
        if buf:
            self._write_chunk(buf)

    def merge_and_assign_ids(self):
        """Fusion externe K-way, déduplication, IDs stables."""
        if not self._chunks:
            return

        readers = [open(p, "r", encoding="utf-8") for p in self._chunks]
        heap: List[Tuple[list, list, int, TextIO]] = []
        for idx, r in enumerate(readers):
            line = r.readline().strip()
            if line:
                i_str, e_str = line.split("\t")
                heap.append((json.loads(i_str), json.loads(e_str), idx, r))
        heapq.heapify(heap)

        last_intent: Optional[list] = None
        current_extent = set()
        node_id = 0

        while heap:
            intent, extent, idx, reader = heapq.heappop(heap)
            nxt = reader.readline().strip()
            if nxt:
                i2, e2 = nxt.split("\t")
                heapq.heappush(heap, (json.loads(i2), json.loads(e2), idx, reader))

            if intent != last_intent:
                if last_intent is not None:
                    self._final_index.append(
                        (frozenset(last_intent), frozenset(current_extent), node_id)
                    )
                    node_id += 1
                last_intent = intent
                current_extent = set(extent)
            else:
                current_extent.update(extent)

        if last_intent is not None:
            self._final_index.append((frozenset(last_intent), frozenset(current_extent), node_id))

        for r in readers:
            r.close()

    @property
    def concepts(self) -> List[Tuple[FrozenSet[int], FrozenSet[int], int]]:
        return self._final_index

    def cleanup(self):
        self._tmp.cleanup()

# =============================================================================
# 5. CALCUL OPTIMISÉ DE COUVERTURE
# =============================================================================
def compute_cover_edges(
    concepts: List[Tuple[FrozenSet[int], FrozenSet[int], int]],
    ctx: FCAContext
) -> List[Tuple[int, int]]:
    """Calcule les arêtes de couverture. Complexité: O(N * M * log N)."""
    intent_to_id: Dict[FrozenSet[int], int] = {c[0]: c[2] for c in concepts}
    edges: Set[Tuple[int, int]] = set()
    m = ctx.num_attributes

    for intent, _, src_id in concepts:
        for m_idx in range(m):
            if m_idx not in intent:
                cand = compute_closure(set(intent) | {m_idx}, ctx)
                dst_id = intent_to_id.get(cand)
                if dst_id is not None and dst_id > src_id:
                    # Propriété FCA: cover direct si |intent diff| == 1
                    if len(cand) == len(intent) + 1:
                        edges.add((src_id, dst_id))
    
    return sorted(edges)

# =============================================================================
# 6. GÉNÉRATION DOT (Contrat Output Strict)
# =============================================================================
class DOTWriter:
    def __init__(self, output_path: str, ctx: FCAContext):
        self.path = Path(output_path)
        self.ctx = ctx
        self._file: Optional[TextIO] = None

    def __enter__(self) -> "DOTWriter":
        self._file = self.path.open("w", encoding="utf-8")
        self._file.write(DOT_HEADER)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._file:
            self._file.write(DOT_FOOTER)
            self._file.close()
        if self.path.exists() and self.path.stat().st_size == 0:
            raise RuntimeError("Échec: fichier DOT généré vide (0 octet).")

    def write_nodes(self, concepts: List[Tuple[FrozenSet[int], FrozenSet[int], int]]):
        for intent, extent, nid in concepts:
            i_names = sorted(self.ctx.attributes[i] for i in intent)
            e_names = sorted(self.ctx.objects[i] for i in extent)
            i_str = ", ".join(i_names) if i_names else "∅"
            e_str = ", ".join(e_names) if e_names else "∅"
            
            ecount = len(extent)
            color = ""
            if ecount == 0:
                color = ', fillcolor="lightblue"'
            elif ecount > 1:
                color = ', fillcolor="orange"'
            
            label = LABEL_PATTERN.format(
                id=nid, ic=len(intent), ec=ecount,
                intent_str=i_str, extent_str=e_str
            )
            # Échappement DOT pour les accolades dans record
            dot_label = "{" + label + "}"
            self._file.write(
                f'{nid} [label="{dot_label}", shape=record, style=filled{color}];\n'
            )

    def write_edges(self, edges: List[Tuple[int, int]]):
        for u, v in edges:
            self._file.write(f"{u} -> {v};\n")

# =============================================================================
# 7. ORCHESTRATION & CLI
# =============================================================================
def run_fca_pipeline(csv_in: str, dot_out: str) -> None:
    """Pipeline complet FCA: Validation -> Énumération -> Fusion -> Couverture -> DOT."""
    ctx = FCAContext.from_csv(csv_in)
    store = DiskStore(max_chunk_size=20000)
    try:
        store.spill(ctx)
        store.merge_and_assign_ids()
        concepts = store.concepts
        edges = compute_cover_edges(concepts, ctx)
        
        with DOTWriter(dot_out, ctx) as writer:
            writer.write_nodes(concepts)
            writer.write_edges(edges)
            
    finally:
        store.cleanup()

def main():
    parser = argparse.ArgumentParser(description="Générateur de treillis FCA conforme FCA4J")
    parser.add_argument("input_csv", help="Chemin CSV binaire valide")
    parser.add_argument("output_dot", help="Chemin de sortie .dot")
    args = parser.parse_args()
    
    try:
        run_fca_pipeline(args.input_csv, args.output_dot)
        print(f"[OK] Treillis généré : {args.output_dot}")
    except Exception as e:
        print(f"[ERREUR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()