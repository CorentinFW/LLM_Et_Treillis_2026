#!/usr/bin/env python3
import argparse
import csv
import gc
import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class FCAContext:
    objects: List[str]
    attributes: List[str]
    obj_attr_bits: List[int]
    attr_obj_bits: List[int]
    all_objects_bits: int
    all_attributes_bits: int


def bit_indices(bits: int) -> Generator[int, None, None]:
    while bits:
        lsb = bits & -bits
        yield lsb.bit_length() - 1
        bits ^= lsb


def bits_to_hex(bits: int) -> str:
    return format(bits, "x")


def hex_to_bits(value: str) -> int:
    if not value:
        return 0
    return int(value, 16)


def estimate_available_ram_bytes() -> int:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return 2 * 1024**3
    try:
        with meminfo.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    value_kib = int(line.split()[1])
                    return value_kib * 1024
    except Exception:
        return 2 * 1024**3
    return 2 * 1024**3


def parse_cell(cell: str) -> int:
    text = cell.strip()
    if text in {"1", "1.0", "true", "True", "TRUE", "x", "X"}:
        return 1
    if text in {"0", "0.0", "false", "False", "FALSE", "", "-"}:
        return 0
    raise ValueError(f"Valeur binaire invalide: '{cell}'")


def load_context(csv_path: str, delimiter: str = ";") -> FCAContext:
    objects: List[str] = []
    attributes: List[str] = []
    obj_attr_bits: List[int] = []

    with open(csv_path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("CSV vide") from exc

        if len(header) < 2:
            raise ValueError("Le CSV doit contenir une colonne objet et au moins un attribut")

        attributes = [a.strip() for a in header[1:]]
        attr_count = len(attributes)

        for line_idx, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != attr_count + 1:
                raise ValueError(
                    f"Ligne {line_idx}: {len(row)} colonnes trouvées, {attr_count + 1} attendues"
                )
            obj = row[0].strip()
            if obj == "":
                raise ValueError(f"Ligne {line_idx}: nom d'objet vide")
            objects.append(obj)
            bits = 0
            for j, cell in enumerate(row[1:]):
                if parse_cell(cell):
                    bits |= 1 << j
            obj_attr_bits.append(bits)

    if not objects:
        raise ValueError("Le contexte ne contient aucun objet")

    object_count = len(objects)
    attr_obj_bits = [0] * len(attributes)
    for obj_idx, attr_bits in enumerate(obj_attr_bits):
        for att_idx in bit_indices(attr_bits):
            attr_obj_bits[att_idx] |= 1 << obj_idx

    all_objects_bits = (1 << object_count) - 1
    all_attributes_bits = (1 << len(attributes)) - 1

    return FCAContext(
        objects=objects,
        attributes=attributes,
        obj_attr_bits=obj_attr_bits,
        attr_obj_bits=attr_obj_bits,
        all_objects_bits=all_objects_bits,
        all_attributes_bits=all_attributes_bits,
    )


def closure(intent_bits: int, ctx: FCAContext) -> Tuple[int, int]:
    extent_bits = ctx.all_objects_bits
    for att_idx in bit_indices(intent_bits):
        extent_bits &= ctx.attr_obj_bits[att_idx]

    closed_intent = ctx.all_attributes_bits
    for obj_idx in bit_indices(extent_bits):
        closed_intent &= ctx.obj_attr_bits[obj_idx]

    return closed_intent, extent_bits


def next_closure(intent_bits: int, ctx: FCAContext) -> Optional[int]:
    m = len(ctx.attributes)
    for i in range(m - 1, -1, -1):
        bit = 1 << i
        if intent_bits & bit:
            continue
        prefix = intent_bits & (bit - 1)
        cand, _ = closure(prefix | bit, ctx)
        lower_mask = bit - 1
        if ((cand & lower_mask) & ~intent_bits) == 0:
            return cand
    return None


def prepare_partition_dirs(base_dir: Path, part_count: int) -> List[Path]:
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    part_dirs: List[Path] = []
    for part_id in range(part_count):
        part_dir = base_dir / f"part{part_id:04d}"
        part_dir.mkdir(parents=True, exist_ok=True)
        part_dirs.append(part_dir)
    return part_dirs


def save_partition(part_dir: Path, chunk_index: int, concepts: List[Dict[str, str]]) -> Path:
    out = part_dir / f"chunk{chunk_index:06d}.json"
    with out.open("w", encoding="utf-8") as handle:
        json.dump(concepts, handle, ensure_ascii=False)
    return out


def choose_partition_count(ctx: FCAContext, ram_bytes: int) -> int:
    object_count = len(ctx.objects)
    attr_count = len(ctx.attributes)
    key_bytes = max(16, (max(object_count, attr_count) + 7) // 8)
    approx_per_concept = 64 + 2 * key_bytes
    target_buffer = max(1, (ram_bytes // 8) // approx_per_concept)
    if target_buffer <= 0:
        return 16
    if len(ctx.attributes) <= 10:
        return 4
    if target_buffer > 2_000_000:
        return 8
    if target_buffer > 500_000:
        return 16
    if target_buffer > 100_000:
        return 32
    return 64


def next_closure_partition(
    ctx: FCAContext,
    partition_root: Path,
    part_count: int,
    chunk_size: int,
) -> Tuple[int, List[int]]:
    part_dirs = prepare_partition_dirs(partition_root, part_count)
    buffers: List[List[Dict[str, str]]] = [[] for _ in range(part_count)]
    chunk_indices: List[int] = [0] * part_count
    concepts_per_part: List[int] = [0] * part_count

    current_intent, current_extent = closure(0, ctx)
    concept_count = 0

    while True:
        part_id = hash(current_intent) % part_count
        buffers[part_id].append(
            {
                "intent": bits_to_hex(current_intent),
                "extent": bits_to_hex(current_extent),
                "intent_size": current_intent.bit_count(),
                "extent_size": current_extent.bit_count(),
            }
        )
        concepts_per_part[part_id] += 1
        concept_count += 1

        if len(buffers[part_id]) >= chunk_size:
            save_partition(part_dirs[part_id], chunk_indices[part_id], buffers[part_id])
            chunk_indices[part_id] += 1
            buffers[part_id].clear()

        nxt = next_closure(current_intent, ctx)
        if nxt is None:
            break
        current_intent, current_extent = closure(nxt, ctx)

    for part_id in range(part_count):
        if buffers[part_id]:
            save_partition(part_dirs[part_id], chunk_indices[part_id], buffers[part_id])
            chunk_indices[part_id] += 1
            buffers[part_id].clear()

    del buffers
    gc.collect()
    return concept_count, concepts_per_part


def load_partitions(
    partition_root: Path,
    part_ids: Optional[Sequence[int]] = None,
    batch_size: int = 2048,
) -> Generator[List[Dict[str, str]], None, None]:
    if part_ids is None:
        part_dirs = sorted(p for p in partition_root.iterdir() if p.is_dir() and p.name.startswith("part"))
    else:
        part_dirs = [partition_root / f"part{part_id:04d}" for part_id in part_ids]

    batch: List[Dict[str, str]] = []
    for part_dir in part_dirs:
        if not part_dir.exists():
            continue
        for chunk_file in sorted(part_dir.glob("chunk*.json")):
            with chunk_file.open("r", encoding="utf-8") as handle:
                concepts = json.load(handle)
            for concept in concepts:
                batch.append(concept)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
    if batch:
        yield batch


def create_sqlite_store(db_path: Path) -> sqlite3.Connection:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute(
        """
        CREATE TABLE concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent_bits TEXT NOT NULL UNIQUE,
            extent_bits TEXT NOT NULL,
            intent_size INTEGER NOT NULL,
            extent_size INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_concepts_intent_size ON concepts(intent_size)")
    conn.execute(
        """
        CREATE TABLE concept_attrs (
            concept_id INTEGER NOT NULL,
            attr_idx INTEGER NOT NULL,
            PRIMARY KEY (concept_id, attr_idx)
        )
        """
    )
    conn.execute("CREATE INDEX idx_concept_attrs_attr ON concept_attrs(attr_idx)")
    conn.commit()
    return conn


def ingest_partitions_to_sqlite(
    partition_root: Path,
    db_path: Path,
    group_parts: int,
    ingest_batch_size: int = 4096,
) -> int:
    conn = create_sqlite_store(db_path)
    inserted = 0
    part_dirs = sorted(p for p in partition_root.iterdir() if p.is_dir() and p.name.startswith("part"))
    all_part_ids = [int(p.name.replace("part", "")) for p in part_dirs]

    if group_parts <= 0:
        group_parts = 1

    for start_idx in range(0, len(all_part_ids), group_parts):
        group = all_part_ids[start_idx : start_idx + group_parts]
        for batch in load_partitions(
            partition_root,
            part_ids=group,
            batch_size=ingest_batch_size,
        ):
            rows = [
                (
                    concept["intent"],
                    concept["extent"],
                    int(concept["intent_size"]),
                    int(concept["extent_size"]),
                )
                for concept in batch
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO concepts(intent_bits, extent_bits, intent_size, extent_size) VALUES (?, ?, ?, ?)",
                rows,
            )
            conn.commit()

    cursor = conn.execute("SELECT id, intent_bits FROM concepts ORDER BY id")
    for concept_id, intent_hex in cursor:
        intent_bits = hex_to_bits(intent_hex)
        attrs = [(concept_id, att_idx) for att_idx in bit_indices(intent_bits)]
        if attrs:
            conn.executemany(
                "INSERT OR IGNORE INTO concept_attrs(concept_id, attr_idx) VALUES (?, ?)",
                attrs,
            )
            inserted += len(attrs)
    conn.commit()
    total_concepts = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    conn.close()
    return total_concepts


def format_elapsed(seconds: float) -> str:
    total = int(seconds)
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {sec:02d}s"
    return f"{minutes}m {sec:02d}s"


def log_progress(start_time: float, progress_percent: float, message: str, done: bool = False) -> None:
    elapsed = format_elapsed(time.time() - start_time)
    pct = max(0.0, min(100.0, progress_percent))
    suffix = "terminé." if done else "en cours..."
    print(f"[Temps: {elapsed}] [Avancement: {pct:.1f}%] {message} {suffix}")


def candidate_rows_for_intent(
    conn: sqlite3.Connection,
    concept_id: int,
    intent_bits: int,
) -> List[Tuple[int, str, int]]:
    attrs = list(bit_indices(intent_bits))
    if not attrs:
        cursor = conn.execute(
            "SELECT id, intent_bits, intent_size FROM concepts WHERE id != ? ORDER BY intent_size ASC, id ASC",
            (concept_id,),
        )
        return cursor.fetchall()

    placeholders = ",".join("?" for _ in attrs)
    query = f"""
        SELECT c.id, c.intent_bits, c.intent_size
        FROM concepts c
        JOIN concept_attrs ca ON c.id = ca.concept_id
        WHERE c.id != ?
          AND ca.attr_idx IN ({placeholders})
        GROUP BY c.id
        HAVING COUNT(DISTINCT ca.attr_idx) = ?
        ORDER BY c.intent_size ASC, c.id ASC
    """
    params: List[int] = [concept_id] + attrs + [len(attrs)]
    cursor = conn.execute(query, params)
    return cursor.fetchall()


def compute_edges(
    db_path: Path,
    edges_path: Path,
    progress_interval_seconds: int = 600,
) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA temp_store=FILE")

    total_concepts = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    start = time.time()
    next_tick = start + progress_interval_seconds

    processed = 0
    comparisons_done = 0
    avg_candidates = 0.0
    edge_count = 0

    if edges_path.exists():
        edges_path.unlink()

    with edges_path.open("w", encoding="utf-8") as out:
        concept_cursor = conn.execute(
            "SELECT id, intent_bits FROM concepts ORDER BY intent_size ASC, id ASC"
        )
        for concept_id, intent_hex in concept_cursor:
            intent_bits = hex_to_bits(intent_hex)
            candidates = candidate_rows_for_intent(conn, concept_id, intent_bits)

            covers: List[Tuple[int, int]] = []
            for cand_id, cand_hex, _cand_size in candidates:
                cand_bits = hex_to_bits(cand_hex)
                comparisons_done += 1
                if cand_bits == intent_bits:
                    continue
                if (cand_bits & intent_bits) != intent_bits:
                    continue

                blocked = False
                for _, kept_bits in covers:
                    if (cand_bits & kept_bits) == kept_bits and cand_bits != kept_bits:
                        blocked = True
                        break
                if not blocked:
                    covers.append((cand_id, cand_bits))

            for target_id, _ in covers:
                out.write(json.dumps({"src": target_id, "dst": concept_id}) + "\n")
                edge_count += 1

            processed += 1
            candidate_count = len(candidates)
            avg_candidates = (
                candidate_count
                if processed == 1
                else ((avg_candidates * (processed - 1)) + candidate_count) / processed
            )

            now = time.time()
            while now >= next_tick:
                estimated_total = max(1.0, total_concepts * max(1.0, avg_candidates))
                progress = min(99.9, (comparisons_done / estimated_total) * 100.0)
                log_progress(start, progress, "Calcul des relations de couverture")
                next_tick += progress_interval_seconds

    log_progress(start, 100.0, "Calcul des relations de couverture", done=True)
    conn.close()
    return edge_count


def concept_id_for_intent(conn: sqlite3.Connection, intent_bits: int) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM concepts WHERE intent_bits = ?",
        (bits_to_hex(intent_bits),),
    ).fetchone()
    return None if row is None else int(row[0])


def build_reduced_labels(
    conn: sqlite3.Connection,
    ctx: FCAContext,
) -> Tuple[Dict[int, List[str]], Dict[int, List[str]]]:
    own_attrs: Dict[int, List[str]] = {}
    own_objs: Dict[int, List[str]] = {}

    for att_idx, att_name in enumerate(ctx.attributes):
        intent_bits, _ = closure(1 << att_idx, ctx)
        concept_id = concept_id_for_intent(conn, intent_bits)
        if concept_id is None:
            continue
        own_attrs.setdefault(concept_id, []).append(att_name)

    for obj_idx, obj_name in enumerate(ctx.objects):
        obj_intent = ctx.obj_attr_bits[obj_idx]
        intent_bits, _ = closure(obj_intent, ctx)
        concept_id = concept_id_for_intent(conn, intent_bits)
        if concept_id is None:
            continue
        own_objs.setdefault(concept_id, []).append(obj_name)

    for values in own_attrs.values():
        values.sort()
    for values in own_objs.values():
        values.sort()

    return own_attrs, own_objs


def write_dot(
    db_path: Path,
    edges_path: Path,
    dot_path: Path,
    ctx: FCAContext,
) -> None:
    conn = sqlite3.connect(str(db_path))
    own_attrs, own_objs = build_reduced_labels(conn, ctx)

    dot_path.parent.mkdir(parents=True, exist_ok=True)
    with dot_path.open("w", encoding="utf-8") as out:
        out.write("digraph G {\n")
        out.write("rankdir=BT;\n\n")

        cursor = conn.execute(
            "SELECT id, intent_size, extent_size FROM concepts ORDER BY intent_size ASC, id ASC"
        )
        for concept_id, intent_size, extent_size in cursor:
            attrs = own_attrs.get(concept_id, [])
            objs = own_objs.get(concept_id, [])
            displayed_obj_count = len(objs)

            attrs_txt = ", ".join(attrs)
            objs_txt = ", ".join(objs)
            label = f"{{{concept_id} (I: {intent_size}, E: {extent_size})|{attrs_txt}|{objs_txt}}}"

            if displayed_obj_count == 0:
                out.write(
                    f"{concept_id} [shape=record,style=filled,fillcolor=lightblue,label=\"{label}\"];\n"
                )
            elif displayed_obj_count > 1:
                out.write(
                    f"{concept_id} [shape=record,style=filled,fillcolor=orange,label=\"{label}\"];\n"
                )
            else:
                out.write(f"{concept_id} [shape=record,label=\"{label}\"];\n")

        out.write("\n")
        if edges_path.exists():
            with edges_path.open("r", encoding="utf-8") as edges_file:
                for line in edges_file:
                    line = line.strip()
                    if not line:
                        continue
                    edge = json.loads(line)
                    out.write(f"{edge['src']} -> {edge['dst']};\n")

        out.write("}\n")

    conn.close()


def choose_chunk_size(ram_bytes: int) -> int:
    if ram_bytes < 512 * 1024**2:
        return 512
    if ram_bytes < 2 * 1024**3:
        return 2048
    if ram_bytes < 8 * 1024**3:
        return 8192
    return 16384


def choose_group_parts(part_count: int, ram_bytes: int) -> int:
    if ram_bytes < 2 * 1024**3:
        return 1
    if ram_bytes < 8 * 1024**3:
        return min(4, part_count)
    return min(8, part_count)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcul de treillis de concepts formels avec contrôle mémoire"
    )
    parser.add_argument("csv_path", help="Chemin du CSV de contexte formel")
    parser.add_argument(
        "--delimiter",
        default=";",
        help="Délimiteur CSV (défaut: ';')",
    )
    parser.add_argument(
        "--partitions",
        type=int,
        default=0,
        help="Nombre de partitions (0 = auto)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        help="Nombre de concepts par chunk JSON (0 = auto)",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=600,
        help="Intervalle de log progression (secondes, défaut 600)",
    )
    args = parser.parse_args()

    start_global = time.time()
    print(f"Démarrage: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_global))}")

    csv_path = Path(args.csv_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {csv_path}")

    ram_bytes = estimate_available_ram_bytes()
    ctx = load_context(str(csv_path), delimiter=args.delimiter)

    part_count = args.partitions if args.partitions > 0 else choose_partition_count(ctx, ram_bytes)
    chunk_size = args.chunk_size if args.chunk_size > 0 else choose_chunk_size(ram_bytes)

    work_root = csv_path.parent
    partition_root = work_root / "partition"
    lattice_dir = work_root / "Lattice"
    dot_path = lattice_dir / f"{csv_path.stem}_LLM.dot"
    db_path = partition_root / "concepts.sqlite"
    edges_path = partition_root / "edges.jsonl"

    print(
        f"Contexte: |G|={len(ctx.objects)}, |M|={len(ctx.attributes)} | RAM dispo estimée={ram_bytes / (1024**3):.2f} GiB"
    )
    print(f"Partitions={part_count}, chunk_size={chunk_size}")

    total_concepts, concepts_per_part = next_closure_partition(
        ctx=ctx,
        partition_root=partition_root,
        part_count=part_count,
        chunk_size=chunk_size,
    )
    print(f"Concepts énumérés (brut): {total_concepts}")

    del concepts_per_part
    gc.collect()

    group_parts = choose_group_parts(part_count, ram_bytes)
    print(f"Fusion partitions par groupes de {group_parts}")
    merged_count = ingest_partitions_to_sqlite(partition_root, db_path, group_parts=group_parts)
    print(f"Concepts distincts après fusion: {merged_count}")

    edge_count = compute_edges(
        db_path=db_path,
        edges_path=edges_path,
        progress_interval_seconds=max(1, args.progress_interval),
    )
    print(f"Arêtes de couverture: {edge_count}")

    write_dot(db_path=db_path, edges_path=edges_path, dot_path=dot_path, ctx=ctx)

    total_elapsed = format_elapsed(time.time() - start_global)
    print(f"Terminé en {total_elapsed}")
    print(dot_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        sys.exit(1)