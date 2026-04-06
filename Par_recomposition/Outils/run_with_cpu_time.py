#!/usr/bin/env python3
"""run_with_cpu_time.py — Run an existing Python algorithm and print CPU time.

Usage example:
python3 Outils/run_with_cpu_time.py Claude_Opus-4.6/Python/lattice2.py Claude_Opus-4.6/Python/eg9_9/eg9_9.csv >> TimeRecord/eg20_20/Claude_Opus-4.6_result.txt 2>&1

Goal
----
Measure *CPU time* (not wall-clock) consumed by a target algorithm, without
modifying the algorithm code.

Supported targets
-----------------
- Script path:         python run_with_cpu_time.py path/to/algo.py -- <args>
- Module ("-m" style): python run_with_cpu_time.py package.module --mode module -- <args>
- Callable entrypoint: python run_with_cpu_time.py package.module:main --mode call -- <args>

Notes
-----
- By default, CPU time is measured with time.process_time() (CPU time of the
  current process: user+sys). This matches the requirement "CPU du processus
  courant".
- On Unix (Linux/macOS), if Python's stdlib module `resource` is available, this
  wrapper can also report user/sys CPU times via getrusage(). With
  --include-children, it adds RUSAGE_CHILDREN (CPU time of *terminated* child
  processes) to report a total.

Limitations
-----------
- time.process_time() does NOT include CPU time spent in other processes.
- resource.getrusage(RUSAGE_CHILDREN) only accounts for *waited* children.
  Long-running children still alive at exit may not be fully counted.

The timing summary is printed in a `finally` block, so it is shown even if the
algorithm raises an exception.
"""

from __future__ import annotations

import argparse
import importlib
import os
import runpy
import sys
import time
from dataclasses import dataclass
from types import ModuleType
from typing import Callable, Optional

try:
    import resource  # Unix only
except Exception:  # pragma: no cover
    resource = None  # type: ignore


@dataclass(frozen=True)
class _RUsage:
    user_s: float
    sys_s: float


@dataclass(frozen=True)
class _CpuSnapshot:
    process_time_s: float
    self_rusage: Optional[_RUsage]
    children_rusage: Optional[_RUsage]


def _get_rusage(who: int) -> Optional[_RUsage]:
    if resource is None:
        return None
    ru = resource.getrusage(who)
    return _RUsage(user_s=float(ru.ru_utime), sys_s=float(ru.ru_stime))


def _take_cpu_snapshot(include_children: bool) -> _CpuSnapshot:
    self_ru = _get_rusage(resource.RUSAGE_SELF) if resource is not None else None
    children_ru = None
    if include_children and resource is not None and hasattr(resource, "RUSAGE_CHILDREN"):
        children_ru = _get_rusage(resource.RUSAGE_CHILDREN)
    return _CpuSnapshot(
        process_time_s=time.process_time(),
        self_rusage=self_ru,
        children_rusage=children_ru,
    )


def _format_seconds(value: float) -> str:
    return f"{value:.6f} s"


def _print_cpu_report(start: _CpuSnapshot, end: _CpuSnapshot, *, include_children: bool) -> None:
    # Output policy (per requirements):
    # - Default: exactly ONE line at the end.
    # - With --include-children (Unix + resource available): up to 3 lines
    #   (self / children / total).

    if include_children and start.self_rusage is not None and end.self_rusage is not None:
        self_user = end.self_rusage.user_s - start.self_rusage.user_s
        self_sys = end.self_rusage.sys_s - start.self_rusage.sys_s
        self_cpu = self_user + self_sys
        print(f"CPU time (self): {_format_seconds(self_cpu)}", file=sys.stderr, flush=True)

        if start.children_rusage is None or end.children_rusage is None:
            # resource may be missing or RUSAGE_CHILDREN unsupported.
            return

        child_user = end.children_rusage.user_s - start.children_rusage.user_s
        child_sys = end.children_rusage.sys_s - start.children_rusage.sys_s
        child_cpu = child_user + child_sys
        total = self_cpu + child_cpu

        print(f"CPU time (children): {_format_seconds(child_cpu)}", file=sys.stderr, flush=True)
        print(f"CPU time (total): {_format_seconds(total)}", file=sys.stderr, flush=True)
        return

    # Default: portable CPU time for the current process.
    delta_proc = end.process_time_s - start.process_time_s
    print(f"CPU time (self): {_format_seconds(delta_proc)}", file=sys.stderr, flush=True)


def _normalize_exit_code(code: object) -> int:
    # Mirrors CPython behavior for sys.exit().
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    # Non-int codes print to stderr and use exit code 1.
    print(code, file=sys.stderr)
    return 1


def _run_as_script(script_path: str, algo_argv: list[str]) -> int:
    script_path = os.path.abspath(script_path)
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    old_argv = sys.argv[:]
    old_sys_path0 = sys.path[0] if sys.path else ""

    # Try to emulate `python path/to/script.py ...`:
    # - sys.argv[0] is the script path
    # - sys.path[0] is the script directory
    sys.argv = [script_path, *algo_argv]
    script_dir = os.path.dirname(script_path)
    if sys.path:
        sys.path[0] = script_dir
    else:
        sys.path.insert(0, script_dir)

    try:
        try:
            runpy.run_path(script_path, run_name="__main__")
        except SystemExit as e:
            return _normalize_exit_code(e.code)
        return 0
    finally:
        sys.argv = old_argv
        if sys.path:
            sys.path[0] = old_sys_path0


def _run_as_module(module_name: str, algo_argv: list[str]) -> int:
    old_argv = sys.argv[:]
    sys.argv = [module_name, *algo_argv]
    try:
        try:
            # alter_sys=True more closely matches `python -m module ...`.
            runpy.run_module(module_name, run_name="__main__", alter_sys=True)
        except SystemExit as e:
            return _normalize_exit_code(e.code)
        return 0
    finally:
        sys.argv = old_argv


def _resolve_callable(target: str) -> tuple[ModuleType, Callable[[], object]]:
    """Resolve `package.module:func` to a zero-arg callable."""
    if ":" not in target:
        raise ValueError("Callable target must be of the form 'package.module:callable'")
    module_name, attr = target.split(":", 1)
    if not module_name or not attr:
        raise ValueError("Callable target must be of the form 'package.module:callable'")

    mod = importlib.import_module(module_name)
    fn = getattr(mod, attr)
    if not callable(fn):
        raise TypeError(f"Target is not callable: {module_name}:{attr}")
    return mod, fn  # type: ignore[return-value]


def _run_as_callable(call_target: str, algo_argv: list[str]) -> int:
    # We keep sys.argv consistent with the other modes, because many `main()`
    # implementations parse sys.argv.
    old_argv = sys.argv[:]
    sys.argv = [call_target, *algo_argv]
    try:
        _mod, fn = _resolve_callable(call_target)
        try:
            result = fn()  # Don't invent a new API; call as zero-arg.
        except SystemExit as e:
            return _normalize_exit_code(e.code)

        # If the callable returns an int, treat it as an exit code.
        if isinstance(result, int):
            return result
        return 0
    finally:
        sys.argv = old_argv


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_with_cpu_time.py",
        add_help=True,
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Run an algorithm (script/module/callable) and print CPU time at the end.\n"
            "CPU timing is printed to stderr so stdout remains mostly unchanged."
        ),
    )

    parser.add_argument(
        "target",
        help=(
            "Target to run.\n"
            "- script path: lattice2.py\n"
            "- module name: package.module\n"
            "- callable:    package.module:main"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "script", "module", "call"],
        default="auto",
        help=(
            "How to interpret TARGET. Default: auto\n"
            "- auto:   *.py or existing path => script; contains ':' => call; else => module\n"
            "- script: run TARGET as a script path\n"
            "- module: run TARGET like `python -m TARGET`\n"
            "- call:   run TARGET like `import module; module:callable()`"
        ),
    )
    parser.add_argument(
        "--include-children",
        action="store_true",
        help=(
            "On Unix, also report CPU time for terminated child processes via\n"
            "resource.getrusage(RUSAGE_CHILDREN), and print a total.\n"
            "Limit: only includes children that have terminated and been waited."
        ),
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help=(
            "Arguments passed to the algorithm.\n"
            "Tip: use '--' before algorithm args to avoid ambiguity, e.g.\n"
            "  python run_with_cpu_time.py lattice2.py -- Animals11/Animals11.csv"
        ),
    )

    ns = parser.parse_args(argv)
    # Strip the leading '--' if present in the remainder.
    if ns.args and ns.args[0] == "--":
        ns.args = ns.args[1:]
    return ns


def main(argv: Optional[list[str]] = None) -> int:
    ns = _parse_args(sys.argv[1:] if argv is None else argv)

    mode = ns.mode
    target: str = ns.target
    algo_args: list[str] = list(ns.args)

    if mode == "auto":
        if ":" in target:
            mode = "call"
        elif target.endswith(".py") or os.path.exists(target):
            mode = "script"
        else:
            mode = "module"

    start = _take_cpu_snapshot(include_children=bool(ns.include_children))
    try:
        if mode == "script":
            return _run_as_script(target, algo_args)
        if mode == "module":
            return _run_as_module(target, algo_args)
        if mode == "call":
            return _run_as_callable(target, algo_args)
        raise AssertionError(f"Unhandled mode: {mode}")
    finally:
        end = _take_cpu_snapshot(include_children=bool(ns.include_children))
        _print_cpu_report(start, end, include_children=bool(ns.include_children))


if __name__ == "__main__":
    raise SystemExit(main())
