from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .common import ensure_dir, now_iso, read_json, write_json


def _normalize_case(
    *,
    repo_root: Path,
    raw_dot: Path,
    output_dot: Path,
    timeout_seconds: int,
) -> tuple[str, str]:
    raw_name = raw_dot.name.lower()
    if "full" in raw_name or "/full/" in str(raw_dot).lower():
        ensure_dir(output_dot.parent)
        shutil.copyfile(raw_dot, output_dot)
        return "OK", "already full; copied"

    cmd = [
        "python3",
        str(repo_root / "Outils" / "induced_to_full_dot.py"),
        str(raw_dot),
        str(output_dot),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "CONVERSION_TIMEOUT", "conversion timed out"

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        return "CONVERSION_FAILED", err or "conversion failed"

    if not output_dot.exists():
        return "CONVERSION_FAILED", "output dot missing after conversion"

    return "OK", "converted to full"


def run_normalize_stage(*, repo_root: Path, run_dir: Path, timeout_seconds: int = 300) -> dict[str, Any]:
    execution_index_path = run_dir / "metadata" / "execution_index.json"
    if not execution_index_path.exists():
        raise FileNotFoundError(f"Missing execution index: {execution_index_path}")

    execution_index = read_json(execution_index_path)
    execution_results = execution_index.get("results", [])

    normalize_dir = ensure_dir(run_dir / "normalize")
    dots_dir = ensure_dir(normalize_dir / "dots")

    results: list[dict[str, Any]] = []

    for entry in execution_results:
        algorithm_id = entry["algorithm_id"]
        dataset_id = entry["dataset_id"]
        case_id = f"{algorithm_id}__{dataset_id}"
        out_json = normalize_dir / f"{case_id}.json"
        out_dot = dots_dir / f"{case_id}_full.dot"

        raw_dot_path = entry.get("raw_dot_copy")
        if not raw_dot_path:
            payload = {
                "algorithm_id": algorithm_id,
                "dataset_id": dataset_id,
                "status": "MISSING_RAW_DOT",
                "message": "raw DOT not available from execution stage",
                "raw_dot": None,
                "normalized_dot": None,
            }
            write_json(out_json, payload)
            results.append(payload)
            continue

        raw_dot = Path(raw_dot_path)
        if not raw_dot.exists():
            payload = {
                "algorithm_id": algorithm_id,
                "dataset_id": dataset_id,
                "status": "MISSING_RAW_DOT",
                "message": f"raw DOT path does not exist: {raw_dot}",
                "raw_dot": str(raw_dot),
                "normalized_dot": None,
            }
            write_json(out_json, payload)
            results.append(payload)
            continue

        status, message = _normalize_case(
            repo_root=repo_root,
            raw_dot=raw_dot,
            output_dot=out_dot,
            timeout_seconds=timeout_seconds,
        )
        payload = {
            "algorithm_id": algorithm_id,
            "dataset_id": dataset_id,
            "status": status,
            "message": message,
            "raw_dot": str(raw_dot),
            "normalized_dot": str(out_dot) if out_dot.exists() else None,
        }
        write_json(out_json, payload)
        results.append(payload)

    index = {
        "stage": "normalize",
        "generated_at": now_iso(),
        "total_cases": len(results),
        "results": results,
    }
    write_json(run_dir / "metadata" / "normalize_index.json", index)
    return index
