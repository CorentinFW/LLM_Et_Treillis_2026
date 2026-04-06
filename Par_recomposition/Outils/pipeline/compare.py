from __future__ import annotations

import itertools
import json
import subprocess
from pathlib import Path
from typing import Any

from .common import ensure_dir, now_iso, read_json, write_json


def run_compare_stage(*, repo_root: Path, run_dir: Path, timeout_seconds: int = 300) -> dict[str, Any]:
    normalize_index_path = run_dir / "metadata" / "normalize_index.json"
    if not normalize_index_path.exists():
        raise FileNotFoundError(f"Missing normalize index: {normalize_index_path}")

    normalize_index = read_json(normalize_index_path)
    entries = normalize_index.get("results", [])

    by_dataset: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry.get("status") != "OK" or not entry.get("normalized_dot"):
            continue
        by_dataset.setdefault(entry["dataset_id"], []).append(entry)

    compare_dir = ensure_dir(run_dir / "compare")
    pair_dir = ensure_dir(compare_dir / "pairs")

    pair_results: list[dict[str, Any]] = []
    matrix: dict[str, dict[str, Any]] = {}

    compare_script = repo_root / "Outils" / "compare_lattices.py"

    for dataset_id, records in sorted(by_dataset.items()):
        matrix[dataset_id] = {}
        dataset_dir = ensure_dir(pair_dir / dataset_id)

        for left, right in itertools.combinations(sorted(records, key=lambda x: x["algorithm_id"]), 2):
            left_id = left["algorithm_id"]
            right_id = right["algorithm_id"]
            key = f"{left_id}__vs__{right_id}"
            output_json = dataset_dir / f"{key}.json"

            cmd = [
                "python3",
                str(compare_script),
                left["normalized_dot"],
                right["normalized_dot"],
                "--json",
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                payload = {
                    "dataset_id": dataset_id,
                    "left_algorithm": left_id,
                    "right_algorithm": right_id,
                    "status": "COMPARE_TIMEOUT",
                    "equivalent": None,
                    "stdout": "",
                    "stderr": "compare command timed out",
                }
                write_json(output_json, payload)
                pair_results.append(payload)
                matrix[dataset_id][key] = "TIMEOUT"
                continue

            payload: dict[str, Any] = {
                "dataset_id": dataset_id,
                "left_algorithm": left_id,
                "right_algorithm": right_id,
                "status": "OK" if proc.returncode in (0, 1) else "COMPARE_FAILED",
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "equivalent": None,
                "report": None,
            }

            if proc.returncode in (0, 1):
                try:
                    report = json.loads(proc.stdout)
                    payload["report"] = report
                    payload["equivalent"] = bool(report.get("equivalent"))
                    matrix[dataset_id][key] = payload["equivalent"]
                except json.JSONDecodeError:
                    payload["status"] = "COMPARE_FAILED"
                    payload["stderr"] = (payload["stderr"] or "") + "\ninvalid JSON from compare script"
                    matrix[dataset_id][key] = "INVALID_JSON"
            else:
                matrix[dataset_id][key] = "FAILED"

            write_json(output_json, payload)
            pair_results.append(payload)

    index = {
        "stage": "compare",
        "generated_at": now_iso(),
        "total_pairs": len(pair_results),
        "results": pair_results,
        "equivalence_matrix": matrix,
    }
    write_json(run_dir / "metadata" / "compare_index.json", index)
    write_json(compare_dir / "equivalence_matrix.json", matrix)
    return index
