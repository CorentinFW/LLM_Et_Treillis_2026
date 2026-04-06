from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ensure_dir, now_iso, read_json, write_json


def _load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = read_json(path)
    if isinstance(data, dict):
        return data
    return {}


def _row(values: list[str]) -> str:
    return "| " + " | ".join(values) + " |"


def build_markdown_report(*, run_id: str, run_dir: Path) -> str:
    execution = _load_optional(run_dir / "metadata" / "execution_index.json")
    normalize = _load_optional(run_dir / "metadata" / "normalize_index.json")
    compare = _load_optional(run_dir / "metadata" / "compare_index.json")
    timeout_events = []
    timeout_path = run_dir / "metadata" / "timeout_events.json"
    if timeout_path.exists():
        raw = read_json(timeout_path)
        if isinstance(raw, list):
            timeout_events = raw

    lines: list[str] = []
    lines.append(f"# Rapport pipeline - {run_id}")
    lines.append("")
    lines.append(f"Généré le: {now_iso()}")
    lines.append("")

    lines.append("## Résumé global")
    lines.append("")
    exec_total = execution.get("total_cases", 0)
    norm_total = normalize.get("total_cases", 0)
    comp_total = compare.get("total_pairs", 0)
    lines.append(f"- Cas execution: {exec_total}")
    lines.append(f"- Cas normalize: {norm_total}")
    lines.append(f"- Paires compare: {comp_total}")
    lines.append(f"- Timeouts: {len(timeout_events)}")
    lines.append("")

    lines.append("## Étape execution")
    lines.append("")
    lines.append(_row(["Dataset", "Algo", "Status", "Elapsed(s)", "Timeout", "DOT copié"]))
    lines.append(_row(["---", "---", "---", "---", "---", "---"]))
    for item in execution.get("results", []):
        lines.append(
            _row(
                [
                    str(item.get("dataset_id", "")),
                    str(item.get("algorithm_id", "")),
                    str(item.get("status", "")),
                    str(item.get("elapsed_seconds", "")),
                    "yes" if item.get("timed_out") else "no",
                    "yes" if item.get("raw_dot_copy") else "no",
                ]
            )
        )
    lines.append("")

    lines.append("## Étape normalize")
    lines.append("")
    lines.append(_row(["Dataset", "Algo", "Status", "Message", "DOT normalisé"]))
    lines.append(_row(["---", "---", "---", "---", "---"]))
    for item in normalize.get("results", []):
        lines.append(
            _row(
                [
                    str(item.get("dataset_id", "")),
                    str(item.get("algorithm_id", "")),
                    str(item.get("status", "")),
                    str(item.get("message", "")),
                    "yes" if item.get("normalized_dot") else "no",
                ]
            )
        )
    lines.append("")

    lines.append("## Étape compare")
    lines.append("")
    lines.append(_row(["Dataset", "Pair", "Status", "Equivalent"]))
    lines.append(_row(["---", "---", "---", "---"]))
    for item in compare.get("results", []):
        pair = f"{item.get('left_algorithm', '')} vs {item.get('right_algorithm', '')}"
        eq = item.get("equivalent")
        eq_text = "NA" if eq is None else ("true" if eq else "false")
        lines.append(
            _row(
                [
                    str(item.get("dataset_id", "")),
                    pair,
                    str(item.get("status", "")),
                    eq_text,
                ]
            )
        )
    lines.append("")

    lines.append("## Matrice d'équivalence")
    lines.append("")
    matrix = compare.get("equivalence_matrix", {})
    if matrix:
        for dataset_id, row in sorted(matrix.items()):
            lines.append(f"- {dataset_id}")
            if isinstance(row, dict) and row:
                for key, value in sorted(row.items()):
                    lines.append(f"  - {key}: {value}")
            else:
                lines.append("  - no comparisons")
    else:
        lines.append("Aucune comparaison disponible.")
    lines.append("")

    if timeout_events:
        lines.append("## Timeouts")
        lines.append("")
        lines.append(_row(["Dataset", "Algo", "Timeout(s)", "At"]))
        lines.append(_row(["---", "---", "---", "---"]))
        for event in timeout_events:
            lines.append(
                _row(
                    [
                        str(event.get("dataset_id", "")),
                        str(event.get("algorithm_id", "")),
                        str(event.get("timeout_seconds", "")),
                        str(event.get("at", "")),
                    ]
                )
            )
        lines.append("")

    return "\n".join(lines)


def run_report_stage(*, run_id: str, run_dir: Path) -> dict[str, Any]:
    report_dir = ensure_dir(run_dir / "report")
    report_path = report_dir / "rapport_pipeline.md"

    markdown = build_markdown_report(run_id=run_id, run_dir=run_dir)
    report_path.write_text(markdown + "\n", encoding="utf-8")

    payload = {
        "stage": "report",
        "generated_at": now_iso(),
        "report_path": str(report_path),
    }
    write_json(run_dir / "metadata" / "report_index.json", payload)
    return payload
