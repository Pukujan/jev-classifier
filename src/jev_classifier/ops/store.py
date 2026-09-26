"""SQLite-backed operational store for issue snapshots and discrepancy flags.

GitHub issues/PRs remain the authority. This store is a local execution aid;
the committed ``ops/ledger/`` tree is a readable projection for other agents.
This module does **not** decide proposal winners or arbitration.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

DEFAULT_OPS_DB_PATH = ".ops/ops.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issue_snapshots (
    number INTEGER NOT NULL,
    is_pr INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    author TEXT,
    assignees_json TEXT NOT NULL DEFAULT '[]',
    labels_json TEXT NOT NULL DEFAULT '[]',
    body_excerpt TEXT,
    url TEXT,
    updated_at TEXT,
    synced_at TEXT NOT NULL,
    linked_issue_numbers_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (number, is_pr)
);

CREATE TABLE IF NOT EXISTS discrepancy_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    subject_type TEXT,
    subject_id TEXT,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sync_run_id INTEGER,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source TEXT NOT NULL,
    issue_count INTEGER NOT NULL DEFAULT 0,
    pr_count INTEGER NOT NULL DEFAULT 0,
    discrepancy_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    notes TEXT
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_list(value: Any) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        # already JSON or plain — normalize to list JSON
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            return json.dumps([value], ensure_ascii=False)
        return json.dumps([parsed], ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False)
    return json.dumps([value], ensure_ascii=False)


@dataclass(frozen=True)
class IssueSnapshot:
    number: int
    title: str
    state: str
    is_pr: bool = False
    author: str | None = None
    assignees: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    body_excerpt: str | None = None
    url: str | None = None
    updated_at: str | None = None
    synced_at: str | None = None
    linked_issue_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class DiscrepancyFlag:
    id: int
    kind: str
    detail: str
    subject_type: str | None = None
    subject_id: str | None = None
    created_at: str | None = None
    sync_run_id: int | None = None
    resolved: bool = False


@dataclass(frozen=True)
class SyncRun:
    id: int
    started_at: str
    source: str
    status: str
    finished_at: str | None = None
    issue_count: int = 0
    pr_count: int = 0
    discrepancy_count: int = 0
    notes: str | None = None


class OpsStore:
    """Thin SQLite ops store.

    Default on-disk path: ``.ops/ops.db`` (gitignored). Tests use ``:memory:``.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> OpsStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA_SQL)
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()
        elif int(row["value"]) != SCHEMA_VERSION:
            raise RuntimeError(
                f"ops schema version mismatch: db={row['value']} code={SCHEMA_VERSION}"
            )

    def schema_version(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"]) if row else 0

    # --- sync runs ---

    def begin_sync_run(self, *, source: str, notes: str | None = None) -> int:
        if not source:
            raise ValueError("source is required")
        ts = _utc_now()
        cur = self._conn.execute(
            """
            INSERT INTO sync_runs
                (started_at, finished_at, source, issue_count, pr_count,
                 discrepancy_count, status, notes)
            VALUES (?, NULL, ?, 0, 0, 0, 'running', ?)
            """,
            (ts, source, notes),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def finish_sync_run(
        self,
        run_id: int,
        *,
        status: str = "ok",
        issue_count: int = 0,
        pr_count: int = 0,
        discrepancy_count: int = 0,
        notes: str | None = None,
    ) -> SyncRun:
        ts = _utc_now()
        self._conn.execute(
            """
            UPDATE sync_runs
            SET finished_at = ?, status = ?, issue_count = ?, pr_count = ?,
                discrepancy_count = ?, notes = COALESCE(?, notes)
            WHERE id = ?
            """,
            (ts, status, issue_count, pr_count, discrepancy_count, notes, run_id),
        )
        self._conn.commit()
        run = self.get_sync_run(run_id)
        assert run is not None
        return run

    def get_sync_run(self, run_id: int) -> SyncRun | None:
        row = self._conn.execute(
            "SELECT * FROM sync_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return SyncRun(
            id=row["id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            source=row["source"],
            issue_count=row["issue_count"],
            pr_count=row["pr_count"],
            discrepancy_count=row["discrepancy_count"],
            status=row["status"],
            notes=row["notes"],
        )

    def list_sync_runs(self, *, limit: int = 20) -> list[SyncRun]:
        rows = self._conn.execute(
            "SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            SyncRun(
                id=r["id"],
                started_at=r["started_at"],
                finished_at=r["finished_at"],
                source=r["source"],
                issue_count=r["issue_count"],
                pr_count=r["pr_count"],
                discrepancy_count=r["discrepancy_count"],
                status=r["status"],
                notes=r["notes"],
            )
            for r in rows
        ]

    # --- issue snapshots ---

    def upsert_issue_snapshot(
        self,
        *,
        number: int,
        title: str,
        state: str,
        is_pr: bool = False,
        author: str | None = None,
        assignees: list[str] | tuple[str, ...] | None = None,
        labels: list[str] | tuple[str, ...] | None = None,
        body_excerpt: str | None = None,
        url: str | None = None,
        updated_at: str | None = None,
        linked_issue_numbers: list[int] | tuple[int, ...] | None = None,
        synced_at: str | None = None,
    ) -> IssueSnapshot:
        if number <= 0:
            raise ValueError("number must be positive")
        if not title:
            raise ValueError("title is required")
        if state not in ("open", "closed"):
            raise ValueError("state must be 'open' or 'closed'")
        ts = synced_at or _utc_now()
        self._conn.execute(
            """
            INSERT INTO issue_snapshots
                (number, is_pr, title, state, author, assignees_json, labels_json,
                 body_excerpt, url, updated_at, synced_at, linked_issue_numbers_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(number, is_pr) DO UPDATE SET
                title = excluded.title,
                state = excluded.state,
                author = excluded.author,
                assignees_json = excluded.assignees_json,
                labels_json = excluded.labels_json,
                body_excerpt = excluded.body_excerpt,
                url = excluded.url,
                updated_at = excluded.updated_at,
                synced_at = excluded.synced_at,
                linked_issue_numbers_json = excluded.linked_issue_numbers_json
            """,
            (
                number,
                1 if is_pr else 0,
                title,
                state,
                author,
                _json_list(assignees),
                _json_list(labels),
                body_excerpt,
                url,
                updated_at,
                ts,
                _json_list(linked_issue_numbers),
            ),
        )
        self._conn.commit()
        snap = self.get_issue_snapshot(number, is_pr=is_pr)
        assert snap is not None
        return snap

    def get_issue_snapshot(
        self, number: int, *, is_pr: bool = False
    ) -> IssueSnapshot | None:
        row = self._conn.execute(
            "SELECT * FROM issue_snapshots WHERE number = ? AND is_pr = ?",
            (number, 1 if is_pr else 0),
        ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def list_issue_snapshots(
        self, *, state: str | None = None, is_pr: bool | None = None
    ) -> list[IssueSnapshot]:
        clauses: list[str] = []
        params: list[Any] = []
        if state is not None:
            clauses.append("state = ?")
            params.append(state)
        if is_pr is not None:
            clauses.append("is_pr = ?")
            params.append(1 if is_pr else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM issue_snapshots {where} ORDER BY number",
            params,
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def replace_all_snapshots(self, snapshots: list[IssueSnapshot]) -> None:
        """Replace entire snapshot table (idempotent full sync)."""
        self._conn.execute("DELETE FROM issue_snapshots")
        for snap in snapshots:
            self._conn.execute(
                """
                INSERT INTO issue_snapshots
                    (number, is_pr, title, state, author, assignees_json, labels_json,
                     body_excerpt, url, updated_at, synced_at, linked_issue_numbers_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap.number,
                    1 if snap.is_pr else 0,
                    snap.title,
                    snap.state,
                    snap.author,
                    _json_list(list(snap.assignees)),
                    _json_list(list(snap.labels)),
                    snap.body_excerpt,
                    snap.url,
                    snap.updated_at,
                    snap.synced_at or _utc_now(),
                    _json_list(list(snap.linked_issue_numbers)),
                ),
            )
        self._conn.commit()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> IssueSnapshot:
        assignees = tuple(json.loads(row["assignees_json"] or "[]"))
        labels = tuple(json.loads(row["labels_json"] or "[]"))
        linked = tuple(json.loads(row["linked_issue_numbers_json"] or "[]"))
        return IssueSnapshot(
            number=row["number"],
            title=row["title"],
            state=row["state"],
            is_pr=bool(row["is_pr"]),
            author=row["author"],
            assignees=assignees,
            labels=labels,
            body_excerpt=row["body_excerpt"],
            url=row["url"],
            updated_at=row["updated_at"],
            synced_at=row["synced_at"],
            linked_issue_numbers=tuple(int(x) for x in linked),
        )

    # --- discrepancy flags ---

    def clear_discrepancies(self, *, unresolved_only: bool = True) -> int:
        if unresolved_only:
            cur = self._conn.execute(
                "DELETE FROM discrepancy_flags WHERE resolved = 0"
            )
        else:
            cur = self._conn.execute("DELETE FROM discrepancy_flags")
        self._conn.commit()
        return cur.rowcount

    def add_discrepancy(
        self,
        *,
        kind: str,
        detail: str,
        subject_type: str | None = None,
        subject_id: str | None = None,
        sync_run_id: int | None = None,
    ) -> int:
        if not kind or not detail:
            raise ValueError("kind and detail are required")
        ts = _utc_now()
        cur = self._conn.execute(
            """
            INSERT INTO discrepancy_flags
                (kind, subject_type, subject_id, detail, created_at, sync_run_id, resolved)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (kind, subject_type, subject_id, detail, ts, sync_run_id),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_discrepancies(
        self, *, unresolved_only: bool = True
    ) -> list[DiscrepancyFlag]:
        if unresolved_only:
            rows = self._conn.execute(
                "SELECT * FROM discrepancy_flags WHERE resolved = 0 ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM discrepancy_flags ORDER BY id"
            ).fetchall()
        return [
            DiscrepancyFlag(
                id=r["id"],
                kind=r["kind"],
                subject_type=r["subject_type"],
                subject_id=r["subject_id"],
                detail=r["detail"],
                created_at=r["created_at"],
                sync_run_id=r["sync_run_id"],
                resolved=bool(r["resolved"]),
            )
            for r in rows
        ]

    def resolve_discrepancy(self, flag_id: int) -> bool:
        cur = self._conn.execute(
            "UPDATE discrepancy_flags SET resolved = 1 WHERE id = ?",
            (flag_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0
