"""Tests for scripts/watchdog_storage.py (offline, tmp_path fixtures only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "watchdog_storage.py"

sys.path.insert(0, str(SCRIPT.parent))
import watchdog_storage as ws  # noqa: E402


def _make_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)


def _watched_by_name(report: dict) -> dict[str, dict]:
    return {w["path"]: w for w in report["watched"]}


def test_sizes_mtimes_and_desc_order(tmp_path: Path) -> None:
    _make_file(tmp_path / ".pytest_cache" / "big.bin", 3000)
    _make_file(tmp_path / ".pytest_cache" / "small.bin", 100)
    _make_file(tmp_path / "__pycache__" / "mod.pyc", 1000)
    _make_file(tmp_path / "src" / "thing.py", 500)

    report = ws.build_report(tmp_path, 2048)

    watched = _watched_by_name(report)
    assert watched[".pytest_cache"]["size_bytes"] == 3100
    assert watched["__pycache__"]["size_bytes"] == 1000
    # missing dirs are reported with zero size and null mtime, never omitted
    assert watched[".venv"]["size_bytes"] == 0
    assert watched[".venv"]["mtime"] is None
    assert isinstance(watched[".pytest_cache"]["mtime"], float)
    assert watched[".pytest_cache"]["mtime"] >= (tmp_path / ".pytest_cache" / "big.bin").stat().st_mtime - 1

    sizes = [w["size_bytes"] for w in report["watched"]]
    assert sizes == sorted(sizes, reverse=True)
    # total covers watched dirs AND unwatched working-tree files
    assert report["total_bytes"] == 3000 + 100 + 1000 + 500


def test_status_ok_and_json_shape(tmp_path: Path) -> None:
    _make_file(tmp_path / "README.md", 10)

    report = ws.build_report(tmp_path, 2048)

    assert set(report) >= {"repo_root", "budget_bytes", "status", "total_bytes", "free_bytes", "watched", "large_files"}
    assert report["status"] == "ok"
    assert report["budget_bytes"] == 2048 * 1024 * 1024
    assert report["free_bytes"] > 0
    assert report["large_files"] == []
    assert {w["path"] for w in report["watched"]} == set(ws.WATCHED_DIRS)
    for w in report["watched"]:
        assert set(w) == {"path", "size_bytes", "mtime"}
    # report must be serializable as one JSON line
    assert json.loads(json.dumps(report)) == report


def test_warn_when_near_budget(tmp_path: Path) -> None:
    _make_file(tmp_path / "data" / "blob", 800 * 1024)

    # ~0.78 MB used against a 1 MB budget -> >=75% of budget -> warn.
    report = ws.build_report(tmp_path, budget_mb=1)  # 800KB >= 75% of 1MB
    assert report["status"] == "warn"

    roomy = ws.build_report(tmp_path, budget_mb=2048)
    assert roomy["status"] == "ok"


def test_over_and_exit_codes(tmp_path: Path) -> None:
    _make_file(tmp_path / "data" / "blob", 2 * 1024 * 1024)

    report = ws.build_report(tmp_path, budget_mb=1)
    assert report["status"] == "over"

    rc_over = ws.main(["--repo-root", str(tmp_path), "--budget-mb", "1"])
    assert rc_over != 0

    rc_ok = ws.main(["--repo-root", str(tmp_path), "--budget-mb", "2048"])
    assert rc_ok == 0


def test_large_file_offenders(tmp_path: Path) -> None:
    _make_file(tmp_path / "datasets" / "weights.bin", ws.LARGE_FILE_BYTES + 10)
    _make_file(tmp_path / ".git" / "objects" / "pack.bin", ws.LARGE_FILE_BYTES + 10)

    report = ws.build_report(tmp_path, 2048)

    offenders = report["large_files"]
    # working-tree offenders flagged; .git internals excluded from committed-binary risk
    assert [f["path"] for f in offenders] == ["datasets/weights.bin"]
    assert offenders[0]["size_bytes"] == ws.LARGE_FILE_BYTES + 10
    assert report["status"] == "warn"


def test_min_free_floor_makes_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_file(tmp_path / "file", 10)

    real_disk_usage = ws.shutil.disk_usage

    class FakeUsage:
        free = ws.MIN_FREE_BYTES - 1

    monkeypatch.setattr(ws.shutil, "disk_usage", lambda p: FakeUsage())
    try:
        report = ws.build_report(tmp_path, 2048)
    finally:
        monkeypatch.setattr(ws.shutil, "disk_usage", real_disk_usage)
    assert report["status"] == "over"


def test_cli_single_json_line_and_help(tmp_path: Path) -> None:
    _make_file(tmp_path / ".pytest_cache" / "x", 42)

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path), "--budget-mb", "2048"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)  # exactly one JSON line
    assert payload["status"] in {"ok", "warn"}
    assert _watched_by_name(payload)[".pytest_cache"]["size_bytes"] == 42

    help_proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_proc.returncode == 0
    assert "--budget-mb" in help_proc.stdout
    assert "--repo-root" in help_proc.stdout
