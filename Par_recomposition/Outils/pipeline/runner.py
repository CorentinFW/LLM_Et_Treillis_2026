from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from .common import ensure_dir, now_iso, render_command, select_latest_file, write_json
from .config import Algorithm, Dataset


def _run_command(command: list[str], timeout_seconds: int, cwd: Path) -> dict[str, Any]:
    started_at = now_iso()
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed = time.monotonic() - started
        return {
            "status": "OK" if result.returncode == 0 else "FAILED",
            "returncode": result.returncode,
            "timed_out": False,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "started_at": started_at,
            "finished_at": now_iso(),
            "elapsed_seconds": round(elapsed, 3),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        return {
            "status": "TIMEOUT",
            "returncode": 124,
            "timed_out": True,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nCommand killed after timeout.",
            "started_at": started_at,
            "finished_at": now_iso(),
            "elapsed_seconds": round(elapsed, 3),
        }


def _resolve_csv_path(repo_root: Path, algorithm: Algorithm, dataset: Dataset) -> Path:
    csv_path = algorithm.csv_path_template.format(
        repo_root=repo_root,
        dataset_id=dataset.id,
        dataset_label=dataset.label,
    )
    return Path(csv_path)


def run_execution_stage(
    *,
    repo_root: Path,
    algorithms: list[Algorithm],
    datasets: list[Dataset],
    run_dir: Path,
    global_timeout_seconds: int,
) -> dict[str, Any]:
    execution_dir = ensure_dir(run_dir / "execution")
    logs_dir = ensure_dir(execution_dir / "logs")
    dots_dir = ensure_dir(execution_dir / "dots")

    results: list[dict[str, Any]] = []
    timeout_events: list[dict[str, Any]] = []

    for algorithm in algorithms:
        for dataset in datasets:
            case_id = f"{algorithm.id}__{dataset.id}"
            log_path = logs_dir / f"{case_id}.log"
            json_path = execution_dir / f"{case_id}.json"

            csv_path = _resolve_csv_path(repo_root, algorithm, dataset)
            if not csv_path.exists():
                payload = {
                    "algorithm_id": algorithm.id,
                    "dataset_id": dataset.id,
                    "status": "MISSING_INPUT",
                    "message": f"CSV not found: {csv_path}",
                    "csv_path": str(csv_path),
                    "raw_dot_source": None,
                    "raw_dot_copy": None,
                }
                write_json(json_path, payload)
                log_path.write_text(payload["message"] + "\n", encoding="utf-8")
                results.append(payload)
                continue

            command = render_command(
                algorithm.command_template,
                {
                    "repo_root": repo_root,
                    "dataset_id": dataset.id,
                    "dataset_label": dataset.label,
                    "csv_path": csv_path,
                },
            )
            timeout_seconds = min(global_timeout_seconds, algorithm.timeout_seconds)
            run_payload = _run_command(command, timeout_seconds=timeout_seconds, cwd=repo_root)

            dot_pattern = algorithm.dot_glob_template.format(
                repo_root=repo_root,
                dataset_id=dataset.id,
                dataset_label=dataset.label,
            )
            source_dot = select_latest_file(dot_pattern)
            copied_dot = None
            if source_dot and source_dot.exists():
                copied_dot = dots_dir / f"{case_id}.dot"
                copied_dot.write_bytes(source_dot.read_bytes())

            if run_payload["timed_out"]:
                timeout_events.append(
                    {
                        "algorithm_id": algorithm.id,
                        "dataset_id": dataset.id,
                        "timeout_seconds": timeout_seconds,
                        "at": run_payload["finished_at"],
                    }
                )

            payload = {
                "algorithm_id": algorithm.id,
                "dataset_id": dataset.id,
                "command": command,
                "timeout_seconds": timeout_seconds,
                "csv_path": str(csv_path),
                "status": run_payload["status"],
                "returncode": run_payload["returncode"],
                "timed_out": run_payload["timed_out"],
                "elapsed_seconds": run_payload["elapsed_seconds"],
                "started_at": run_payload["started_at"],
                "finished_at": run_payload["finished_at"],
                "raw_dot_source": str(source_dot) if source_dot else None,
                "raw_dot_copy": str(copied_dot) if copied_dot else None,
                "stdout_log": str(log_path),
            }

            log_text = []
            log_text.append("Command: " + " ".join(command))
            log_text.append("Status: " + payload["status"])
            log_text.append("Elapsed: " + str(payload["elapsed_seconds"]))
            log_text.append("--- STDOUT ---")
            log_text.append(run_payload["stdout"])
            log_text.append("--- STDERR ---")
            log_text.append(run_payload["stderr"])
            log_path.write_text("\n".join(log_text), encoding="utf-8")

            write_json(json_path, payload)
            results.append(payload)

    index = {
        "stage": "execution",
        "generated_at": now_iso(),
        "total_cases": len(results),
        "results": results,
    }
    write_json(run_dir / "metadata" / "execution_index.json", index)
    write_json(run_dir / "metadata" / "timeout_events.json", timeout_events)
    return index
