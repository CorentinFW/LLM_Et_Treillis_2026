from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .common import ensure_dir, now_iso, render_command, select_latest_file, write_json
from .config import Algorithm, Dataset
from .resource_monitor import disk_roots_written_since_size_bytes, sample_resources


def _drain_stream(stream) -> str:
    if stream is None:
        return ""
    try:
        return stream.read()
    except Exception:
        return ""


def _run_command(
    command: list[str],
    timeout_seconds: int | None,
    cwd: Path,
    monitored_roots: list[Path],
) -> dict[str, Any]:
    started_at = now_iso()
    started_time_ns = time.time_ns()
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout_holder: dict[str, str] = {"value": ""}
    stderr_holder: dict[str, str] = {"value": ""}

    stdout_thread = threading.Thread(
        target=lambda: stdout_holder.__setitem__("value", _drain_stream(proc.stdout)),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=lambda: stderr_holder.__setitem__("value", _drain_stream(proc.stderr)),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    peak_rss_bytes = 0
    peak_disk_bytes = 0
    peak_written_live_bytes = 0
    peak_io_read_bytes = 0
    peak_io_write_bytes = 0
    peak_io_rchar_bytes = 0
    peak_io_wchar_bytes = 0
    sample_count = 0
    timed_out = False

    while True:
        sample = sample_resources(root_pid=proc.pid, disk_roots=monitored_roots)
        sample_count += 1
        peak_rss_bytes = max(peak_rss_bytes, sample.rss_bytes)
        peak_disk_bytes = max(peak_disk_bytes, sample.disk_bytes)
        peak_written_live_bytes = max(
            peak_written_live_bytes,
            disk_roots_written_since_size_bytes(monitored_roots, started_time_ns),
        )
        peak_io_read_bytes = max(peak_io_read_bytes, sample.io_read_bytes)
        peak_io_write_bytes = max(peak_io_write_bytes, sample.io_write_bytes)
        peak_io_rchar_bytes = max(peak_io_rchar_bytes, sample.io_rchar_bytes)
        peak_io_wchar_bytes = max(peak_io_wchar_bytes, sample.io_wchar_bytes)

        if proc.poll() is not None:
            break

        if timeout_seconds is not None and (time.monotonic() - started) >= timeout_seconds:
            timed_out = True
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            break

        time.sleep(0.001)

    returncode = proc.wait()

    # Final sample to catch outputs committed right before process exit.
    final_sample = sample_resources(root_pid=proc.pid, disk_roots=monitored_roots)
    sample_count += 1
    peak_rss_bytes = max(peak_rss_bytes, final_sample.rss_bytes)
    peak_disk_bytes = max(peak_disk_bytes, final_sample.disk_bytes)
    peak_written_live_bytes = max(
        peak_written_live_bytes,
        disk_roots_written_since_size_bytes(monitored_roots, started_time_ns),
    )
    peak_io_read_bytes = max(peak_io_read_bytes, final_sample.io_read_bytes)
    peak_io_write_bytes = max(peak_io_write_bytes, final_sample.io_write_bytes)
    peak_io_rchar_bytes = max(peak_io_rchar_bytes, final_sample.io_rchar_bytes)
    peak_io_wchar_bytes = max(peak_io_wchar_bytes, final_sample.io_wchar_bytes)

    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)
    elapsed = time.monotonic() - started

    stdout = stdout_holder["value"]
    stderr = stderr_holder["value"]
    if timed_out:
        stderr = stderr + ("\n" if stderr else "") + "Command killed after timeout."

    return {
        "status": "TIMEOUT" if timed_out else ("OK" if returncode == 0 else "FAILED"),
        "returncode": 124 if timed_out else returncode,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "started_at": started_at,
        "finished_at": now_iso(),
        "elapsed_seconds": round(elapsed, 3),
        "peak_rss_bytes": peak_rss_bytes,
        "peak_disk_bytes": peak_disk_bytes,
        "peak_written_live_bytes": peak_written_live_bytes,
        "peak_io_read_bytes": peak_io_read_bytes,
        "peak_io_write_bytes": peak_io_write_bytes,
        "peak_io_rchar_bytes": peak_io_rchar_bytes,
        "peak_io_wchar_bytes": peak_io_wchar_bytes,
        "monitor_sample_count": sample_count,
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
    global_timeout_seconds: int | None,
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
            timeout_seconds = None if global_timeout_seconds is None else min(global_timeout_seconds, algorithm.timeout_seconds)
            run_payload = _run_command(
                command,
                timeout_seconds=timeout_seconds,
                cwd=repo_root,
                monitored_roots=[csv_path.parent],
            )

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
                        "timeout_enabled": timeout_seconds is not None,
                        "at": run_payload["finished_at"],
                    }
                )

            payload = {
                "algorithm_id": algorithm.id,
                "dataset_id": dataset.id,
                "command": command,
                "timeout_seconds": timeout_seconds,
                "timeout_enabled": timeout_seconds is not None,
                "csv_path": str(csv_path),
                "status": run_payload["status"],
                "returncode": run_payload["returncode"],
                "timed_out": run_payload["timed_out"],
                "elapsed_seconds": run_payload["elapsed_seconds"],
                "started_at": run_payload["started_at"],
                "finished_at": run_payload["finished_at"],
                "peak_rss_bytes": run_payload["peak_rss_bytes"],
                "peak_disk_bytes": run_payload["peak_disk_bytes"],
                "peak_written_live_bytes": run_payload["peak_written_live_bytes"],
                "peak_io_read_bytes": run_payload["peak_io_read_bytes"],
                "peak_io_write_bytes": run_payload["peak_io_write_bytes"],
                "peak_io_rchar_bytes": run_payload["peak_io_rchar_bytes"],
                "peak_io_wchar_bytes": run_payload["peak_io_wchar_bytes"],
                "total_written_bytes": run_payload["peak_io_wchar_bytes"],
                "monitor_sample_count": run_payload["monitor_sample_count"],
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
