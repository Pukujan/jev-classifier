"""Integration tests for the ops_sync -> COORD.md board projection (#22).

ops_sync writes the committed `ops/ledger/COORD.md`; this repo already had one
board-clobber incident (PR #25 -> repair #26), so these tests pin:

  (a) a fixture with comments renders claim/proposal/receipt rows into COORD.md;
  (b) re-running the sync is byte-identical (idempotent projection);
  (c) a comments-less fixture leaves an existing COORD.md untouched (the
      legacy fetch-failure path must never blank the board);
  (d) normalize_comments accepts both gh-shaped (author.login/createdAt) and
      REST-shaped (user.login/created_at/issue_url) comment JSON;
  (e) production default: fixture runs never write the committed board unless
      write_coord is set explicitly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ops_sync  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "ops" / "snapshot.json"


def _sync(tmp_path: Path, fixture: Path, *, write_coord: bool = True) -> Path:
    ops_sync.run_sync(
        fixture=fixture,
        repo="Pukujan/jev-classifier",
        db_path=tmp_path / "ops.db",
        ledger_dir=tmp_path / "ledger",
        current_md_path=None,
        coord_db_path=None,
        write_coord=write_coord,
    )
    return tmp_path / "ledger" / "COORD.md"


def _fixture_without(tmp_path: Path, key: str) -> Path:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.pop(key, None)
    p = tmp_path / "snapshot-nocomments.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_coord_md_renders_projection(tmp_path: Path) -> None:
    coord = _sync(tmp_path, FIXTURE)
    assert coord.is_file()
    text = coord.read_text(encoding="utf-8")
    # proposals table: P-15-1 accepted by the authoritative verdict
    assert "P-15-1" in text and "accepted" in text
    # live claim: the marker claim on open issue #22
    assert "feat/coordination-layer-22" in text
    # settled claim: the prose claim sits on CLOSED #15, so merged/closed
    # release drops it from Live claims (no permanent stale rows)
    assert "feat/grok-source-bot" not in text
    # receipts table renders with per-field provenance sources
    assert "Run receipts" in text and "r-22-1" in text
    assert "A-7f3c (owner_recorded)" in text
    assert "unavailable (unavailable)" in text


def test_coord_md_idempotent(tmp_path: Path) -> None:
    first = _sync(tmp_path, FIXTURE)
    before = first.read_bytes()
    second = _sync(tmp_path, FIXTURE)
    assert before == second.read_bytes(), (
        "COORD.md must be byte-identical across syncs of the same comments; "
        "sync timestamps in the board would churn the committed projection"
    )


def test_comments_less_fixture_preserves_board(tmp_path: Path) -> None:
    coord = _sync(tmp_path, FIXTURE)
    assert coord.is_file()
    protected = coord.read_bytes()
    bare = _fixture_without(tmp_path, "comments")
    _sync(tmp_path, bare)
    assert coord.read_bytes() == protected, (
        "a comments-less (fetch-failed/legacy) sync must not blank COORD.md"
    )


def test_fixture_mode_default_never_writes_board(tmp_path: Path) -> None:
    coord = _sync(tmp_path, FIXTURE, write_coord=False)
    assert not coord.exists(), (
        "run_sync default: only a live (gh) sync may rewrite the committed "
        "coordination board; fixture mode must not"
    )


def test_normalize_comments_both_shapes() -> None:
    rest_shape = {
        "id": 1, "body": "x", "created_at": "2026-09-26T19:00:00Z",
        "user": {"login": "Pukujan"},
        "issue_url": "https://api.github.com/repos/o/r/issues/22",
    }
    gh_shape = {
        "id": 2, "body": "y", "createdAt": "2026-09-26T19:01:00Z",
        "author": {"login": "Pukujan"}, "issue": 15,
    }
    out = ops_sync.normalize_comments([rest_shape, gh_shape])
    assert out[0] == {"body": "x", "author": "Pukujan",
                      "created_at": "2026-09-26T19:00:00Z",
                      "issue": 22, "comment_id": 1}
    assert out[1]["issue"] == 15 and out[1]["created_at"].endswith("01:00Z")
