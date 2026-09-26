"""Offline storage watchdog: read-only disk-usage report for the repo working tree.

Measures the size of the repo working tree plus key cache/artifact directories,
free space on the enclosing volume, and flags large-file offenders (>50 MB) so
agents see committed-binary risk early. Per AGENTS.md: no large binaries or
datasets get committed, and caches stay gitignored.

This tool NEVER deletes anything -- the deletion policy stays human/agent-ruled.
Stdlib only; no network, no dependencies.

Usage:
    python scripts/watchdog_storage.py [--repo-root PATH] [--budget-mb N]

Prints a single line of JSON:
    {"repo_root", "budget_bytes", "status", "total_bytes", "free_bytes",
     "watched": [{"path", "size_bytes", "mtime"}... sorted by size desc],
     "large_files": [{"path", "size_bytes"}... >50 MB, excluding .git/]}

Exit status: 0 when status is ok or warn; 1 when over --budget-mb (default
2048) or free space on the volume drops below 512 MB.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Cache/artifact dirs watched individually (all gitignored per AGENTS.md;
# .git is watched for repo-history bloat, not because it should shrink).
WATCHED_DIRS = (
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".coord",
    ".ops",
    ".research_cache",
    ".git",
)

DEFAULT_BUDGET_MB = 2048
MIN_FREE_BYTES = 512 * 1024 * 1024  # below this -> over (exit non-zero)
WARN_FREE_BYTES = 2 * MIN_FREE_BYTES  # below this -> warn
WARN_BUDGET_RATIO = 0.75  # total at >= 75% of budget -> warn
LARGE_FILE_BYTES = 50 * 1024 * 1024  # committed-binary-risk threshold


def _report_size(repo_root: Path) -> tuple[int, dict[str, int], dict[str, float], list[dict[str, object]]]:
    """Single walk: total tree bytes, per-watched-dir sizes/mtimes, large files.

    Symlinks are not followed and unreadable entries are skipped; nothing on
    disk is modified.
    """
    total = 0
    dir_sizes = {name: 0 for name in WATCHED_DIRS}
    dir_mtimes: dict[str, float] = {}
    large_files: list[dict[str, object]] = []

    for dirpath, dirnames, filenames in os.walk(repo_root, topdown=True, onerror=lambda e: None):
        base = Path(dirpath)
        rel = base.relative_to(repo_root)
        for name in dirnames:
            try:
                st = base.joinpath(name).lstat()
            except OSError:
                continue
            top = rel.parts[0] if rel.parts else name
            if not rel.parts and name in WATCHED_DIRS:
                try:
                    dir_mtimes[name] = max(dir_mtimes.get(name, 0.0), st.st_mtime)
                except OSError:
                    pass
            elif rel.parts and rel.parts[0] in WATCHED_DIRS:
                pass  # subdirectory mtimes below a watched root still count below
            if top in WATCHED_DIRS:
                try:
                    dir_mtimes[top] = max(dir_mtimes.get(top, 0.0), st.st_mtime)
                except OSError:
                    pass
        for name in filenames:
            fp = base.joinpath(name)
            try:
                st = fp.lstat()
            except OSError:
                continue
            if not os.path.islink(fp):
                total += st.st_size
                top = rel.parts[0] if rel.parts else name
                if top in WATCHED_DIRS:
                    dir_sizes[top] += st.st_size
                    dir_mtimes[top] = max(dir_mtimes.get(top, 0.0), st.st_mtime)
                # Committed-binary risk concerns the working tree, not .git internals.
                if st.st_size > LARGE_FILE_BYTES and (not rel.parts or rel.parts[0] != ".git"):
                    large_files.append({"path": (rel / name).as_posix(), "size_bytes": st.st_size})
    return total, dir_sizes, dir_mtimes, large_files


def build_report(repo_root: Path, budget_mb: float) -> dict[str, object]:
    """Compute the watchdog report for ``repo_root`` under a ``budget_mb`` budget."""
    repo_root = repo_root.resolve()
    total, dir_sizes, dir_mtimes, large_files = _report_size(repo_root)
    budget_bytes = int(budget_mb * 1024 * 1024)
    free_bytes = shutil.disk_usage(repo_root).free

    watched = [
        {
            "path": name,
            "size_bytes": dir_sizes[name],
            "mtime": dir_mtimes.get(name),  # None when the dir does not exist
        }
        for name in WATCHED_DIRS
    ]
    watched.sort(key=lambda w: (-w["size_bytes"], w["path"]))

    large_files.sort(key=lambda f: (-f["size_bytes"], f["path"]))

    if total > budget_bytes or free_bytes < MIN_FREE_BYTES:
        status = "over"
    elif (
        total >= WARN_BUDGET_RATIO * budget_bytes
        or free_bytes < WARN_FREE_BYTES
        or large_files
    ):
        status = "warn"
    else:
        status = "ok"

    return {
        "repo_root": str(repo_root),
        "budget_bytes": budget_bytes,
        "status": status,
        "total_bytes": total,
        "free_bytes": free_bytes,
        "watched": watched,
        "large_files": large_files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="watchdog_storage.py",
        description="Read-only storage watchdog (never deletes anything).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="repository root to measure (default: current directory)",
    )
    parser.add_argument(
        "--budget-mb",
        type=float,
        default=DEFAULT_BUDGET_MB,
        help=f"total-size budget in MB (default: {DEFAULT_BUDGET_MB})",
    )
    args = parser.parse_args(argv)

    report = build_report(args.repo_root, args.budget_mb)
    print(json.dumps(report, sort_keys=False))
    return 1 if report["status"] == "over" else 0


if __name__ == "__main__":
    sys.exit(main())
