from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import os


@dataclass(frozen=True)
class ResourceSample:
    rss_bytes: int
    disk_bytes: int
    io_read_bytes: int
    io_write_bytes: int
    io_rchar_bytes: int
    io_wchar_bytes: int


def _page_size_bytes() -> int:
    try:
        return os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return 4096


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _read_process_ppid(pid: int) -> int | None:
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        data = stat_path.read_text(encoding="utf-8")
    except OSError:
        return None

    parts = data.split()
    if len(parts) < 4:
        return None
    return _safe_int(parts[3])


def _read_process_rss_bytes(pid: int, page_size: int) -> int | None:
    statm_path = Path("/proc") / str(pid) / "statm"
    try:
        data = statm_path.read_text(encoding="utf-8").split()
    except OSError:
        return None

    if len(data) < 2:
        return None
    resident_pages = _safe_int(data[1])
    return resident_pages * page_size


def _read_process_io(pid: int) -> tuple[int, int, int, int] | None:
    io_path = Path("/proc") / str(pid) / "io"
    try:
        lines = io_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    read_bytes = 0
    write_bytes = 0
    rchar_bytes = 0
    wchar_bytes = 0
    for line in lines:
        key, sep, raw_value = line.partition(":")
        if not sep:
            continue
        value = _safe_int(raw_value.strip())
        if key == "read_bytes":
            read_bytes = value
        elif key == "write_bytes":
            write_bytes = value
        elif key == "rchar":
            rchar_bytes = value
        elif key == "wchar":
            wchar_bytes = value
    return read_bytes, write_bytes, rchar_bytes, wchar_bytes


def _descendant_pids(root_pid: int) -> list[int]:
    children_by_parent: dict[int, list[int]] = {}

    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        ppid = _read_process_ppid(pid)
        if ppid is None:
            continue
        children_by_parent.setdefault(ppid, []).append(pid)

    result: list[int] = []
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        result.append(current)
        stack.extend(children_by_parent.get(current, []))
    return result


def _directory_size_bytes(root: Path) -> int:
    if not root.exists():
        return 0

    total = 0
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        current_dir = Path(dirpath)
        for filename in filenames:
            file_path = current_dir / filename
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def disk_roots_size_bytes(disk_roots: Iterable[Path]) -> int:
    total = 0
    for root in disk_roots:
        total += _directory_size_bytes(root)
    return total


def disk_roots_written_since_size_bytes(disk_roots: Iterable[Path], since_time_ns: int) -> int:
    total = 0
    for root in disk_roots:
        if not root.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
            current_dir = Path(dirpath)
            for filename in filenames:
                file_path = current_dir / filename
                try:
                    stat = file_path.stat()
                except OSError:
                    continue
                if stat.st_mtime_ns >= since_time_ns:
                    total += stat.st_size
    return total


def sample_resources(*, root_pid: int, disk_roots: Iterable[Path]) -> ResourceSample:
    page_size = _page_size_bytes()
    rss_bytes = 0
    io_read_bytes = 0
    io_write_bytes = 0
    io_rchar_bytes = 0
    io_wchar_bytes = 0

    for pid in _descendant_pids(root_pid):
        rss_value = _read_process_rss_bytes(pid, page_size)
        if rss_value is not None:
            rss_bytes += rss_value

        io_values = _read_process_io(pid)
        if io_values is None:
            continue
        read_bytes, write_bytes, rchar_bytes, wchar_bytes = io_values
        io_read_bytes += read_bytes
        io_write_bytes += write_bytes
        io_rchar_bytes += rchar_bytes
        io_wchar_bytes += wchar_bytes

    disk_bytes = disk_roots_size_bytes(disk_roots)

    return ResourceSample(
        rss_bytes=rss_bytes,
        disk_bytes=disk_bytes,
        io_read_bytes=io_read_bytes,
        io_write_bytes=io_write_bytes,
        io_rchar_bytes=io_rchar_bytes,
        io_wchar_bytes=io_wchar_bytes,
    )