#!/usr/bin/env python3
"""Compile tous les rapport_pipeline.md d'un dossier en un unique markdown.

Exemple:
    python Outils/Donnees/compile_rapports_pipeline.py Outils/outputs/D1

Sortie par defaut:
    Outils/Donnees/D1.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


SECTION_SUMMARY = "Résumé global"
SECTION_EXECUTION = "Étape execution"
SECTION_NORMALIZE = "Étape normalize"
SECTION_COMPARE = "Étape compare"


@dataclass
class ReportData:
    dataset_label: str
    generated_at: str
    summary: Dict[str, str]
    execution_rows: List[Dict[str, str]]
    normalize_rows: List[Dict[str, str]]
    compare_rows: List[Dict[str, str]]
    report_path: Path


def _clean_cell(value: str) -> str:
    return value.strip().strip("`")


def _parse_markdown_table(table_text: str) -> List[Dict[str, str]]:
    lines = [line.strip() for line in table_text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []

    headers = [_clean_cell(col) for col in lines[0].strip("|").split("|")]
    rows: List[Dict[str, str]] = []

    for raw_line in lines[2:]:
        values = [_clean_cell(col) for col in raw_line.strip("|").split("|")]
        if len(values) < len(headers):
            values += [""] * (len(headers) - len(values))
        row = {headers[i]: values[i] for i in range(len(headers))}
        rows.append(row)

    return rows


def _extract_section_block(content: str, section_title: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(section_title)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group("body").strip() if match else ""


def _extract_summary_map(section_body: str) -> Dict[str, str]:
    summary: Dict[str, str] = {}
    for line in section_body.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        # Format attendu: - Clé: valeur
        pair = line[1:].strip()
        if ":" not in pair:
            continue
        key, value = pair.split(":", 1)
        summary[key.strip()] = value.strip()
    return summary


def _extract_first_table(section_body: str) -> List[Dict[str, str]]:
    table_lines = [line for line in section_body.splitlines() if line.strip().startswith("|")]
    if not table_lines:
        return []
    return _parse_markdown_table("\n".join(table_lines))


def _dataset_from_rows(*tables: List[Dict[str, str]]) -> str:
    for rows in tables:
        for row in rows:
            value = row.get("Dataset", "").strip()
            if value:
                return value
    return ""


def _parse_report(report_path: Path) -> ReportData:
    content = report_path.read_text(encoding="utf-8")

    date_match = re.search(r"^Généré le:\s*(.+)$", content, re.MULTILINE)
    generated_at = date_match.group(1).strip() if date_match else "n/a"

    summary_body = _extract_section_block(content, SECTION_SUMMARY)
    execution_body = _extract_section_block(content, SECTION_EXECUTION)
    normalize_body = _extract_section_block(content, SECTION_NORMALIZE)
    compare_body = _extract_section_block(content, SECTION_COMPARE)

    execution_rows = _extract_first_table(execution_body)
    normalize_rows = _extract_first_table(normalize_body)
    compare_rows = _extract_first_table(compare_body)

    title_match = re.search(r"^#\s+Rapport pipeline\s+-\s+(.+)$", content, re.MULTILINE)
    title_fallback = title_match.group(1).strip() if title_match else report_path.parent.parent.name
    dataset_label = _dataset_from_rows(execution_rows, normalize_rows, compare_rows) or title_fallback

    return ReportData(
        dataset_label=dataset_label,
        generated_at=generated_at,
        summary=_extract_summary_map(summary_body),
        execution_rows=execution_rows,
        normalize_rows=normalize_rows,
        compare_rows=compare_rows,
        report_path=report_path,
    )


def _parse_elapsed(value: str) -> float:
    try:
        return float(value.strip())
    except Exception:
        return float("inf")


def _alphanum_key(value: str) -> List[object]:
    parts = re.split(r"(\d+)", value.casefold())
    key: List[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        elif part:
            key.append(part)
    return key


def _sorted_algos(execution_rows: List[Dict[str, str]]) -> List[str]:
    algos = {row.get("Algo", "").strip() for row in execution_rows if row.get("Algo", "").strip()}
    return sorted(algos, key=_algo_order_key)


def _algo_order_key(algo: str) -> tuple[int, List[object]]:
    # Force FCA4J en premier, puis tri alphanumerique pour le reste.
    priority = 0 if algo.strip().lower() == "fca4j" else 1
    return (priority, _alphanum_key(algo))


def _algo_metric_value(execution_rows: List[Dict[str, str]], algo: str, column: str) -> str:
    for row in execution_rows:
        if row.get("Algo", "").strip() == algo:
            if row.get("Status", "").strip().upper() != "OK":
                return "FAILED"
            return row.get(column, "").strip() or "n/a"
    return "n/a"


def _rel_path(path: Path, launch_dir: Path) -> str:
    return os.path.relpath(path, launch_dir)


def _equivalent_algo_count(report: ReportData) -> int:
    ok_algos = {
        row.get("Algo", "").strip()
        for row in report.execution_rows
        if row.get("Status", "").strip().upper() == "OK" and row.get("Algo", "").strip()
    }
    if not ok_algos:
        return 0

    parent = {algo: algo for algo in ok_algos}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for row in report.compare_rows:
        if row.get("Equivalent", "").strip().lower() != "true":
            continue
        pair = row.get("Pair", "")
        if " vs " not in pair:
            continue
        left, right = [part.strip() for part in pair.split(" vs ", 1)]
        if left in ok_algos and right in ok_algos:
            union(left, right)

    component_sizes: Dict[str, int] = {}
    for algo in ok_algos:
        root = find(algo)
        component_sizes[root] = component_sizes.get(root, 0) + 1

    return max(component_sizes.values()) if component_sizes else 0


def _build_global_table(reports: List[ReportData]) -> str:
    all_algos = sorted(
        {algo for report in reports for algo in _sorted_algos(report.execution_rows)},
        key=_algo_order_key,
    )

    columns = ["Dataset", "OK exec (réussi/échec)", "Nb d'algo équivalents"]
    columns.extend([f"Temps {algo} (s)" for algo in all_algos])
    columns.extend([f"RAM {algo}" for algo in all_algos])
    columns.extend([f"Disque max {algo}" for algo in all_algos])

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, sep]

    for report in reports:
        ok_exec = sum(1 for row in report.execution_rows if row.get("Status", "").upper() == "OK")
        fail_exec = len(report.execution_rows) - ok_exec
        eq_algo_count = _equivalent_algo_count(report)
        row_values = [report.dataset_label, f"{ok_exec}/{fail_exec}", str(eq_algo_count)]
        row_values.extend([_algo_metric_value(report.execution_rows, algo, "Elapsed(s)") for algo in all_algos])
        row_values.extend([_algo_metric_value(report.execution_rows, algo, "RAM max") for algo in all_algos])
        row_values.extend([_algo_metric_value(report.execution_rows, algo, "Disque max") for algo in all_algos])
        lines.append("| " + " | ".join(row_values) + " |")

    return "\n".join(lines)


def _rows_to_markdown(rows: List[Dict[str, str]], preferred_columns: List[str]) -> str:
    if not rows:
        return "_Aucune donnée._"

    columns = [col for col in preferred_columns if col in rows[0]]
    if not columns:
        columns = list(rows[0].keys())

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(row.get(col, "") for col in columns) + " |" for row in rows]
    return "\n".join([header, sep] + body)


def _build_output_markdown(input_dir: Path, reports: List[ReportData], launch_dir: Path) -> str:
    generated = dt.datetime.now().isoformat(timespec="seconds")
    lines: List[str] = []

    lines.append(f"# Compilation pipeline - {input_dir.name}")
    lines.append("")
    lines.append(f"Généré le: {generated}")
    lines.append(f"Dossier source: {_rel_path(input_dir, launch_dir)}")
    lines.append(f"Rapports compilés: {len(reports)}")
    lines.append("")

    lines.append("## Vue synthétique")
    lines.append("")
    lines.append(_build_global_table(reports))
    lines.append("")

    lines.append("## Détails par dataset")
    lines.append("")

    for report in reports:
        lines.append(f"### {report.dataset_label}")
        lines.append("")
        lines.append(f"- Source: {_rel_path(report.report_path, launch_dir)}")
        lines.append(f"- Généré le: {report.generated_at}")

        if report.summary:
            summary_inline = " ; ".join(f"{k}: {v}" for k, v in report.summary.items())
            lines.append(f"- Résumé: {summary_inline}")

        lines.append("")
        lines.append("#### Execution")
        lines.append("")
        lines.append(
            _rows_to_markdown(
                report.execution_rows,
                [
                    "Dataset",
                    "Algo",
                    "Status",
                    "Elapsed(s)",
                    "RAM max",
                    "Disque max",
                    "I/O lecture",
                    "I/O écriture",
                    "Timeout",
                    "DOT copié",
                ],
            )
        )
        lines.append("")

        lines.append("#### Normalize")
        lines.append("")
        lines.append(
            _rows_to_markdown(
                report.normalize_rows,
                ["Dataset", "Algo", "Status", "Message", "DOT normalisé"],
            )
        )
        lines.append("")

        lines.append("#### Compare")
        lines.append("")
        lines.append(
            _rows_to_markdown(
                report.compare_rows,
                ["Dataset", "Pair", "Status", "Equivalent"],
            )
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def compile_reports(input_dir: Path, output_dir: Path, launch_dir: Path) -> Path:
    report_paths = sorted(input_dir.glob("*/report/rapport_pipeline.md"))
    if not report_paths:
        raise FileNotFoundError(f"Aucun rapport trouvé dans {input_dir} (attendu: */report/rapport_pipeline.md)")

    reports = [_parse_report(path) for path in report_paths]
    reports.sort(key=lambda r: _alphanum_key(r.dataset_label))

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_dir.name}.md"
    output_path.write_text(_build_output_markdown(input_dir, reports, launch_dir), encoding="utf-8")
    return output_path


def main() -> None:
    launch_dir = Path.cwd().resolve()
    parser = argparse.ArgumentParser(description="Compile les rapport_pipeline.md en un seul markdown comparatif.")
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Dossier à compiler (ex: Outils/outputs/D1).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Dossier de sortie (défaut: Outils/Donnees).",
    )
    args = parser.parse_args()

    output_path = compile_reports(args.input_dir.resolve(), args.output_dir.resolve(), launch_dir)
    print(f"Compilation terminée: {output_path}")


if __name__ == "__main__":
    main()
