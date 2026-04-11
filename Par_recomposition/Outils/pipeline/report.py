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


def _format_bytes(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "NA"

    size = float(value)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def _aggregate_execution_resources(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for item in results:
        algorithm_id = str(item.get("algorithm_id", ""))
        if not algorithm_id:
            continue

        bucket = summary.setdefault(
            algorithm_id,
            {
                "cases": 0,
                "peak_rss_bytes": 0,
                "peak_disk_bytes": 0,
                "peak_written_live_bytes": 0,
                "peak_io_read_bytes": 0,
                "peak_io_write_bytes": 0,
                "total_written_bytes": 0,
            },
        )
        bucket["cases"] += 1
        bucket["peak_rss_bytes"] = max(bucket["peak_rss_bytes"], int(item.get("peak_rss_bytes") or 0))
        bucket["peak_disk_bytes"] = max(bucket["peak_disk_bytes"], int(item.get("peak_disk_bytes") or 0))
        bucket["peak_written_live_bytes"] = max(bucket["peak_written_live_bytes"], int(item.get("peak_written_live_bytes") or 0))
        bucket["peak_io_read_bytes"] = max(bucket["peak_io_read_bytes"], int(item.get("peak_io_read_bytes") or 0))
        bucket["peak_io_write_bytes"] = max(bucket["peak_io_write_bytes"], int(item.get("peak_io_write_bytes") or 0))
        bucket["total_written_bytes"] = max(bucket["total_written_bytes"], int(item.get("total_written_bytes") or 0))
    return summary


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

    lines.append("## Ressources par algorithme")
    lines.append("")
    lines.append("- RAM = RSS maximum observé pendant l'exécution.")
    lines.append("- Disque max = total d'octets écrits pendant l'exécution (cumul `wchar`).")
    lines.append("- Disque dossier pic = pic de taille totale du dossier surveillé (somme de tous les fichiers présents à cet instant, y compris les partitions).")
    lines.append("- Disque écrit pic = pic de taille des fichiers modifiés/créés pendant l'exécution et encore présents à cet instant.")
    lines.append("- I/O = volumes observés via /proc pendant l'exécution.")
    lines.append("")
    lines.append(_row(["Algo", "Cas", "RAM max", "Disque max", "Disque dossier pic", "Disque écrit pic", "I/O lecture max", "I/O écriture max"]))
    lines.append(_row(["---", "---", "---", "---", "---", "---", "---", "---"]))
    resource_summary = _aggregate_execution_resources(list(execution.get("results", [])))
    for algorithm_id, values in sorted(resource_summary.items()):
        lines.append(
            _row(
                [
                    algorithm_id,
                    str(values.get("cases", 0)),
                    _format_bytes(values.get("peak_rss_bytes")),
                    _format_bytes(values.get("total_written_bytes")),
                    _format_bytes(values.get("peak_disk_bytes")),
                    _format_bytes(values.get("peak_written_live_bytes")),
                    _format_bytes(values.get("peak_io_read_bytes")),
                    _format_bytes(values.get("peak_io_write_bytes")),
                ]
            )
        )
    lines.append("")

    lines.append("## Étape execution")
    lines.append("")
    lines.append(_row(["Dataset", "Algo", "Status", "Elapsed(s)", "RAM max", "Disque max", "Disque dossier pic", "Disque écrit pic", "I/O lecture", "I/O écriture", "Timeout", "DOT copié"]))
    lines.append(_row(["---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---"]))
    for item in execution.get("results", []):
        lines.append(
            _row(
                [
                    str(item.get("dataset_id", "")),
                    str(item.get("algorithm_id", "")),
                    str(item.get("status", "")),
                    str(item.get("elapsed_seconds", "")),
                    _format_bytes(item.get("peak_rss_bytes")),
                    _format_bytes(item.get("total_written_bytes")),
                    _format_bytes(item.get("peak_disk_bytes")),
                    _format_bytes(item.get("peak_written_live_bytes")),
                    _format_bytes(item.get("peak_io_read_bytes")),
                    _format_bytes(item.get("peak_io_write_bytes")),
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
