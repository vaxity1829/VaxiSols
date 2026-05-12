from __future__ import annotations

from pathlib import Path
import os
import time


def _existing(paths: list[Path]) -> list[Path]:
    return [p for p in paths if p.exists() and p.is_file()]


def list_biome_scan_log_paths(username: str | None = None, max_candidates: int = 14) -> list[Path]:
    """Return likely Roblox/Bloxstrap/Fishstrap log files, newest first."""
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates: list[Path] = []
    scan_dirs = [
        local / "Roblox" / "logs",
        local / "Bloxstrap" / "Logs",
        local / "Fishstrap" / "Logs",
    ]
    for d in scan_dirs:
        if not d.exists():
            continue
        for p in d.glob("*.log"):
            candidates.append(p)

    now = time.time()
    week = 7 * 24 * 60 * 60
    recent = []
    for p in _existing(candidates):
        try:
            if now - p.stat().st_mtime <= week:
                recent.append(p)
        except OSError:
            continue

    recent.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return recent[: max(1, max_candidates)]


def read_file_tail(path: Path, max_bytes: int = 512 * 1024) -> str:
    """Read up to `max_bytes` from end of a text file."""
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            take = min(size, max_bytes)
            f.seek(size - take)
            data = f.read(take)
        return data.decode("utf-8", errors="ignore")
    except OSError:
        return ""
