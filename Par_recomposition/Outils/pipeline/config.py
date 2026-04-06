from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import read_json
from . import STAGES


@dataclass(frozen=True)
class Algorithm:
    id: str
    label: str
    csv_path_template: str
    command_template: str
    dot_glob_template: str
    timeout_seconds: int


@dataclass(frozen=True)
class Dataset:
    id: str
    label: str
    tags: list[str]


@dataclass(frozen=True)
class RunSettings:
    selected_algorithms: list[str]
    selected_datasets: list[str]
    stages: list[str]
    timeout_seconds: int
    continue_on_error: bool


@dataclass(frozen=True)
class LoadedConfig:
    algorithms: dict[str, Algorithm]
    datasets: dict[str, Dataset]
    run: RunSettings


def _must_str(data: dict[str, Any], key: str, source: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}: missing or invalid '{key}'")
    return value.strip()


def _must_int(data: dict[str, Any], key: str, source: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{source}: missing or invalid positive int '{key}'")
    return value


def _must_list_str(data: dict[str, Any], key: str, source: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{source}: missing or invalid list[str] '{key}'")
    return value


def load_pipeline_config(config_dir: Path) -> LoadedConfig:
    algorithms_path = config_dir / "algorithms.json"
    datasets_path = config_dir / "datasets.json"
    run_path = config_dir / "run.json"

    algorithms_data = read_json(algorithms_path)
    datasets_data = read_json(datasets_path)
    run_data = read_json(run_path)

    raw_algorithms = algorithms_data.get("algorithms")
    if not isinstance(raw_algorithms, list) or not raw_algorithms:
        raise ValueError("algorithms.json: 'algorithms' must be a non-empty list")

    raw_datasets = datasets_data.get("datasets")
    if not isinstance(raw_datasets, list) or not raw_datasets:
        raise ValueError("datasets.json: 'datasets' must be a non-empty list")

    algorithms: dict[str, Algorithm] = {}
    for index, entry in enumerate(raw_algorithms):
        source = f"algorithms.json:algorithms[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{source}: expected object")
        algo = Algorithm(
            id=_must_str(entry, "id", source),
            label=_must_str(entry, "label", source),
            csv_path_template=_must_str(entry, "csv_path_template", source),
            command_template=_must_str(entry, "command_template", source),
            dot_glob_template=_must_str(entry, "dot_glob_template", source),
            timeout_seconds=_must_int(entry, "timeout_seconds", source),
        )
        if algo.id in algorithms:
            raise ValueError(f"Duplicate algorithm id: {algo.id}")
        algorithms[algo.id] = algo

    datasets: dict[str, Dataset] = {}
    for index, entry in enumerate(raw_datasets):
        source = f"datasets.json:datasets[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{source}: expected object")
        tags = entry.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError(f"{source}: invalid 'tags' (expected list[str])")
        ds = Dataset(
            id=_must_str(entry, "id", source),
            label=_must_str(entry, "label", source),
            tags=tags,
        )
        if ds.id in datasets:
            raise ValueError(f"Duplicate dataset id: {ds.id}")
        datasets[ds.id] = ds

    source = "run.json"
    run = RunSettings(
        selected_algorithms=_must_list_str(run_data, "selected_algorithms", source),
        selected_datasets=_must_list_str(run_data, "selected_datasets", source),
        stages=_must_list_str(run_data, "stages", source),
        timeout_seconds=_must_int(run_data, "timeout_seconds", source),
        continue_on_error=bool(run_data.get("continue_on_error", True)),
    )

    unknown_algos = [a for a in run.selected_algorithms if a not in algorithms]
    if unknown_algos:
        raise ValueError(f"run.json: unknown selected_algorithms: {unknown_algos}")

    unknown_datasets = [d for d in run.selected_datasets if d not in datasets]
    if unknown_datasets:
        raise ValueError(f"run.json: unknown selected_datasets: {unknown_datasets}")

    unknown_stages = [s for s in run.stages if s not in STAGES]
    if unknown_stages:
        raise ValueError(f"run.json: unknown stages: {unknown_stages}")

    return LoadedConfig(algorithms=algorithms, datasets=datasets, run=run)
