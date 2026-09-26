"""Tests for OpsStore schema, idempotent sync, discrepancy detection, secret redaction."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from jev_classifier.ops import OpsStore
from jev_classifier.ops.store import SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "ops" / "snapshot.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "ops_sync.py"


def test_ops_schema_and_version() -> None:
    with OpsStore(":memory:") as store:
        assert store.schema_version() == SCHEMA_VERSION
        # tables usable
        run_id = store.begin_sync_run(source="test")
        assert run_id >= 1
        snap = store.upsert_issue_snapshot(
            number=18,
            title="ops ledger",
            state="open",
            assignees=["Pukujan"],
            labels=["ops"],
        )
        assert snap.number == 18
        assert snap.assignees == ("Pukujan",)
        again = store.upsert_issue_snapshot(
            number=18,
            title="ops ledger updated",
            state="open",
        )
        assert again.title == "ops ledger updated"
        assert store.get_issue_snapshot(18) is not None
        flag_id = store.add_discrepancy(
            kind="open_pr_without_linked_issue",
            detail="PR #20 has no linked issue",
            subject_type="pr",
            subject_id="20",
            sync_run_id=run_id,
        )
        assert flag_id >= 1
        store.finish_sync_run(
            run_id, status="ok", issue_count=1, pr_count=0, discrepancy_count=1
        )
        run = store.get_sync_run(run_id)
        assert run is not None
        assert run.status == "ok"
        assert run.discrepancy_count == 1
        flags = store.list_discrepancies()
        assert len(flags) == 1
        assert flags[0].kind == "open_pr_without_linked_issue"


def test_idempotent_sync_with_fixture(tmp_path: Path) -> None:
    db = tmp_path / "ops.db"
    ledger = tmp_path / "ledger"
    cmd = [
        sys.executable,
        str(SYNC_SCRIPT),
        "--fixture",
        str(FIXTURE),
        "--db",
        str(db),
        "--ledger-dir",
        str(ledger),
        "--json",
    ]
    first = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(REPO_ROOT))
    r1 = json.loads(first.stdout)
    assert r1["ok"] is True
    assert r1["issue_count"] == 4
    assert r1["pr_count"] == 3
    assert r1["discrepancy_count"] >= 3

    issue_log_1 = (ledger / "ISSUE_LOG.md").read_text(encoding="utf-8")
    disc_1 = (ledger / "DISCREPANCIES.md").read_text(encoding="utf-8")
    json_files_1 = sorted(p.name for p in (ledger / "issues").glob("*.json"))

    second = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(REPO_ROOT))
    r2 = json.loads(second.stdout)
    assert r2["ok"] is True
    assert r2["issue_count"] == r1["issue_count"]
    assert r2["pr_count"] == r1["pr_count"]
    assert r2["discrepancy_count"] == r1["discrepancy_count"]

    issue_log_2 = (ledger / "ISSUE_LOG.md").read_text(encoding="utf-8")
    disc_2 = (ledger / "DISCREPANCIES.md").read_text(encoding="utf-8")
    json_files_2 = sorted(p.name for p in (ledger / "issues").glob("*.json"))

    # Idempotent projection: same issue/PR set and discrepancy kinds
    assert json_files_1 == json_files_2
    assert "#18" in issue_log_2 and "#18" in issue_log_1
    assert "open_pr_without_linked_issue" in disc_1
    assert "open_pr_without_linked_issue" in disc_2

    with OpsStore(db) as store:
        # One unresolved set after second sync (cleared then re-added)
        flags = store.list_discrepancies(unresolved_only=True)
        assert len(flags) == r2["discrepancy_count"]
        runs = store.list_sync_runs()
        assert len(runs) >= 2
        assert all(r.status == "ok" for r in runs[:2])


def test_discrepancy_detection_kinds(tmp_path: Path) -> None:
    # Import detectors directly
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    # Load module by path
    import importlib.util

    spec = importlib.util.spec_from_file_location("ops_sync", SYNC_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snaps = mod.snapshots_from_payload(payload)
    flags = mod.detect_discrepancies(
        snaps,
        current_md=payload["current_md"],
        coord_claims=payload["coord_claims"],
    )
    kinds = {f["kind"] for f in flags}
    assert "open_pr_without_linked_issue" in kinds
    assert "current_md_vs_open_issues" in kinds
    assert "ownership_collision_stub" in kinds
    assert "closed_issue_still_claimed" in kinds

    # Specific subjects
    by_kind: dict[str, list[dict]] = {}
    for f in flags:
        by_kind.setdefault(f["kind"], []).append(f)
    assert any(f["subject_id"] == "20" for f in by_kind["open_pr_without_linked_issue"])
    assert any(f["subject_id"] == "99" for f in by_kind["current_md_vs_open_issues"])
    assert any(f["subject_id"] == "15" for f in by_kind["ownership_collision_stub"])
    assert any(f["subject_id"] == "3" for f in by_kind["closed_issue_still_claimed"])


def test_no_secrets_in_ledger_output(tmp_path: Path) -> None:
    db = tmp_path / "ops.db"
    ledger = tmp_path / "ledger"
    subprocess.run(
        [
            sys.executable,
            str(SYNC_SCRIPT),
            "--fixture",
            str(FIXTURE),
            "--db",
            str(db),
            "--ledger-dir",
            str(ledger),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    forbidden = [
        "sk-secretvaluehere",
        "supersecretTOKEN123",
        "OPENROUTER_API_KEY=sk-",
        "api_key=supersecret",
    ]
    texts: list[str] = []
    texts.append((ledger / "ISSUE_LOG.md").read_text(encoding="utf-8"))
    texts.append((ledger / "DISCREPANCIES.md").read_text(encoding="utf-8"))
    texts.append((ledger / "README.md").read_text(encoding="utf-8"))
    for p in (ledger / "issues").glob("*.json"):
        texts.append(p.read_text(encoding="utf-8"))
    blob = "\n".join(texts)
    for bad in forbidden:
        assert bad not in blob, f"secret-like material leaked: {bad!r}"
    # Redaction markers or absence is fine; body excerpts may contain [REDACTED]
    assert "sk-secret" not in blob.lower() or "[REDACTED]" in blob
