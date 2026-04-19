#!/usr/bin/env python3
"""Normalize CSV files for llm/Chatgpt5.3Codex/C++/concept_lattice.

Normalization rules:
- output delimiter is ';'
- first header cell is forced to empty
- UTF-8 BOM in first header cell is removed
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def detect_delimiter(sample: str) -> str:
    """Detect CSV delimiter, falling back to a simple heuristic."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        if dialect.delimiter in {",", ";"}:
            return dialect.delimiter
    except csv.Error:
        pass

    return ";" if sample.count(";") >= sample.count(",") else ","


def normalize_csv(input_path: Path, output_path: Path) -> tuple[int, int]:
    with input_path.open("r", encoding="utf-8", newline="") as src:
        sample = src.read(8192)
        src.seek(0)
        delimiter = detect_delimiter(sample)
        rows = list(csv.reader(src, delimiter=delimiter))

    if not rows:
        raise ValueError(f"CSV vide: {input_path}")

    if not rows[0]:
        rows[0] = [""]

    rows[0][0] = rows[0][0].lstrip("\ufeff")
    rows[0][0] = ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter=";", lineterminator="\n")
        writer.writerows(rows)

    return len(rows), len(rows[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalise un CSV pour concept_lattice (separateur ';')."
    )
    parser.add_argument("input_csv", type=Path, help="Chemin du CSV source")
    parser.add_argument(
        "output_csv",
        nargs="?",
        type=Path,
        help="Chemin du CSV normalise (defaut: <input>_normalized.csv)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path: Path = args.input_csv
    output_path: Path = (
        args.output_csv
        if args.output_csv is not None
        else input_path.with_name(f"{input_path.stem}_normalized.csv")
    )

    if not input_path.exists():
        parser.error(f"Fichier introuvable: {input_path}")

    try:
        row_count, col_count = normalize_csv(input_path, output_path)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows  : {row_count}")
    print(f"Cols  : {col_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
