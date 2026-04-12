#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline import STAGES
from pipeline.common import default_run_id, ensure_dir, now_iso, resolve_repo_root, write_json
from pipeline.compare import run_compare_stage
from pipeline.config import LoadedConfig, load_pipeline_config
from pipeline.normalize import run_normalize_stage
from pipeline.report import run_report_stage
from pipeline.runner import run_execution_stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline modulaire de comparaison des algorithmes de treillis")
    parser.add_argument(
        "--config-dir",
        default="Outils/config",
        help="Dossier de configuration JSON (algorithms.json, datasets.json, run.json)",
    )
    parser.add_argument("--run-id", default="", help="Identifiant du run (défaut: timestamp)")
    parser.add_argument(
        "--stage",
        choices=["all", *STAGES],
        default="all",
        help="Étape à lancer indépendamment ou all",
    )
    parser.add_argument(
        "--only-algos",
        nargs="*",
        default=None,
        help="Limiter aux algorithmes fournis (IDs de config)",
    )
    parser.add_argument(
        "--only-datasets",
        nargs="*",
        default=None,
        help="Limiter aux datasets fournis (IDs de config)",
    )
    parser.add_argument("--resume", action="store_true", help="Autoriser un run_id existant")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=None,
        help="Continuer même si une étape échoue",
    )
    timeout_group = parser.add_mutually_exclusive_group()
    timeout_group.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="Remplacer le timeout d'exécution global par une nouvelle limite en secondes",
    )
    timeout_group.add_argument(
        "--no-timeout",
        action="store_true",
        help="Désactiver le timeout d'exécution global pour les algorithmes",
    )
    return parser.parse_args()


def effective_selection(config: LoadedConfig, args: argparse.Namespace):
    selected_algo_ids = args.only_algos if args.only_algos is not None else config.run.selected_algorithms
    selected_dataset_ids = args.only_datasets if args.only_datasets is not None else config.run.selected_datasets

    algorithms = []
    for algo_id in selected_algo_ids:
        if algo_id not in config.algorithms:
            raise ValueError(f"Unknown algorithm id: {algo_id}")
        algorithms.append(config.algorithms[algo_id])

    datasets = []
    for dataset_id in selected_dataset_ids:
        if dataset_id not in config.datasets:
            raise ValueError(f"Unknown dataset id: {dataset_id}")
        datasets.append(config.datasets[dataset_id])

    return algorithms, datasets


def main() -> int:
    args = parse_args()

    script_path = Path(__file__).resolve()
    repo_root = resolve_repo_root(script_path.parent)
    config_dir = (repo_root / args.config_dir).resolve()

    config = load_pipeline_config(config_dir)
    algorithms, datasets = effective_selection(config, args)

    run_id = args.run_id or default_run_id()
    run_dir = repo_root / "Outils" / "outputs" / run_id

    if run_dir.exists() and not args.resume:
        if any(run_dir.iterdir()):
            raise FileExistsError(
                f"Run directory already exists and is not empty: {run_dir}. Use --resume or another --run-id."
            )

    ensure_dir(run_dir)
    metadata_dir = ensure_dir(run_dir / "metadata")
    ensure_dir(metadata_dir)

    continue_on_error = config.run.continue_on_error
    if args.continue_on_error:
        continue_on_error = True

    if args.no_timeout:
        execution_timeout_seconds = None
        timeout_mode = "disabled"
    elif args.timeout_seconds is not None:
        if args.timeout_seconds <= 0:
            raise ValueError("--timeout-seconds must be a positive integer")
        execution_timeout_seconds = args.timeout_seconds
        timeout_mode = "custom"
    else:
        execution_timeout_seconds = config.run.timeout_seconds
        timeout_mode = "config"

    run_meta = {
        "run_id": run_id,
        "created_at": now_iso(),
        "repo_root": str(repo_root),
        "config_dir": str(config_dir),
        "selected_algorithms": [algo.id for algo in algorithms],
        "selected_datasets": [ds.id for ds in datasets],
        "timeout_seconds": execution_timeout_seconds,
        "timeout_mode": timeout_mode,
        "continue_on_error": continue_on_error,
    }
    write_json(metadata_dir / "run_meta.json", run_meta)

    if args.stage == "all":
        stages = config.run.stages
    else:
        stages = [args.stage]

    stage_status: dict[str, str] = {}

    for stage in stages:
        try:
            if stage == "execution":
                run_execution_stage(
                    repo_root=repo_root,
                    algorithms=algorithms,
                    datasets=datasets,
                    run_dir=run_dir,
                    global_timeout_seconds=execution_timeout_seconds,
                )
            elif stage == "normalize":
                run_normalize_stage(repo_root=repo_root, run_dir=run_dir)
            elif stage == "compare":
                run_compare_stage(repo_root=repo_root, run_dir=run_dir)
            elif stage == "report":
                run_report_stage(run_id=run_id, run_dir=run_dir)
            else:
                raise ValueError(f"Unsupported stage: {stage}")
            stage_status[stage] = "OK"
        except Exception as exc:  # noqa: BLE001
            stage_status[stage] = f"FAILED: {exc}"
            if not continue_on_error:
                break

    summary = {
        "run_id": run_id,
        "finished_at": now_iso(),
        "stages_requested": stages,
        "stage_status": stage_status,
    }
    write_json(metadata_dir / "summary.json", summary)

    # Non-zero if any requested stage failed.
    return 0 if all(value == "OK" for value in stage_status.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
