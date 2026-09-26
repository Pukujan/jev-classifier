"""SQLite-backed coordination: checkpoints, ownership claims, send-log, collision flags.

GitHub issues/PRs remain the authority. This store is a local execution aid so
agents can share idempotent progress keys and detect ownership collisions without
replacing issue/PR workflow.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_key TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ownership (
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    released_at TEXT,
    PRIMARY KEY (resource_type, resource_id)
);

CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    target TEXT NOT NULL,
    summary TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collision_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    agent_id TEXT,
    other_agent_id TEXT,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);
"""


class CollisionError(Exception):
    """Raised when an ownership claim collides with a different agent."""

    def __init__(
        self,
        message: str,
        *,
        resource_type: str,
        resource_id: str,
        holder_agent_id: str,
        claimant_agent_id: str,
    ) -> None:
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.holder_agent_id = holder_agent_id
        self.claimant_agent_id = claimant_agent_id


@dataclass(frozen=True)
class CheckpointResult:
    checkpoint_key: str
    inserted: bool
    agent_id: str
    created_at: str


@dataclass(frozen=True)
class OwnershipClaim:
    resource_type: str
    resource_id: str
    agent_id: str
    status: str
    claimed_at: str
    released_at: str | None = None


@dataclass(frozen=True)
class OwnershipResult:
    claim: OwnershipClaim
    inserted: bool
    collision: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CoordStore:
    """Thin SQLite coordination store.

    Default path is under the caller's chosen location (typically
    ``.coord/agents.db``, gitignored). In-memory ``:memory:`` is supported for tests.
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

    def __enter__(self) -> CoordStore:
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
                f"coord schema version mismatch: db={row['value']} code={SCHEMA_VERSION}"
            )

    # --- checkpoints (idempotent by key) ---

    def put_checkpoint(
        self,
        checkpoint_key: str,
        *,
        agent_id: str,
        issue_number: int | None = None,
        pr_number: int | None = None,
        payload_json: str | None = None,
    ) -> CheckpointResult:
        if not checkpoint_key or not agent_id:
            raise ValueError("checkpoint_key and agent_id are required")
        existing = self._conn.execute(
            "SELECT agent_id, created_at FROM checkpoints WHERE checkpoint_key = ?",
            (checkpoint_key,),
        ).fetchone()
        if existing is not None:
            return CheckpointResult(
                checkpoint_key=checkpoint_key,
                inserted=False,
                agent_id=existing["agent_id"],
                created_at=existing["created_at"],
            )
        ts = _utc_now()
        self._conn.execute(
            """
            INSERT INTO checkpoints
                (checkpoint_key, agent_id, issue_number, pr_number, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (checkpoint_key, agent_id, issue_number, pr_number, payload_json, ts),
        )
        self._conn.commit()
        return CheckpointResult(
            checkpoint_key=checkpoint_key,
            inserted=True,
            agent_id=agent_id,
            created_at=ts,
        )

    def get_checkpoint(self, checkpoint_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM checkpoints WHERE checkpoint_key = ?",
            (checkpoint_key,),
        ).fetchone()
        return dict(row) if row else None

    # --- ownership claims ---

    def claim_ownership(
        self,
        *,
        resource_type: Literal["issue", "pr", "sub_issue", "branch"],
        resource_id: str,
        agent_id: str,
        raise_on_collision: bool = True,
    ) -> OwnershipResult:
        if not resource_id or not agent_id:
            raise ValueError("resource_id and agent_id are required")
        existing = self._conn.execute(
            """
            SELECT * FROM ownership
            WHERE resource_type = ? AND resource_id = ?
            """,
            (resource_type, resource_id),
        ).fetchone()
        if existing is not None and existing["status"] == "active":
            if existing["agent_id"] == agent_id:
                claim = OwnershipClaim(
                    resource_type=existing["resource_type"],
                    resource_id=existing["resource_id"],
                    agent_id=existing["agent_id"],
                    status=existing["status"],
                    claimed_at=existing["claimed_at"],
                    released_at=existing["released_at"],
                )
                return OwnershipResult(claim=claim, inserted=False, collision=False)
            self._flag_collision(
                kind="ownership_collision",
                resource_type=resource_type,
                resource_id=resource_id,
                agent_id=agent_id,
                other_agent_id=existing["agent_id"],
                detail=(
                    f"agent {agent_id!r} tried to claim {resource_type}/{resource_id} "
                    f"held by {existing['agent_id']!r}"
                ),
            )
            if raise_on_collision:
                raise CollisionError(
                    f"ownership collision on {resource_type}/{resource_id}: "
                    f"held by {existing['agent_id']!r}, claimed by {agent_id!r}",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    holder_agent_id=existing["agent_id"],
                    claimant_agent_id=agent_id,
                )
            claim = OwnershipClaim(
                resource_type=existing["resource_type"],
                resource_id=existing["resource_id"],
                agent_id=existing["agent_id"],
                status=existing["status"],
                claimed_at=existing["claimed_at"],
                released_at=existing["released_at"],
            )
            return OwnershipResult(claim=claim, inserted=False, collision=True)

        ts = _utc_now()
        if existing is not None and existing["status"] == "released":
            self._conn.execute(
                """
                UPDATE ownership
                SET agent_id = ?, status = 'active', claimed_at = ?, released_at = NULL
                WHERE resource_type = ? AND resource_id = ?
                """,
                (agent_id, ts, resource_type, resource_id),
            )
            self._conn.commit()
            claim = OwnershipClaim(
                resource_type=resource_type,
                resource_id=resource_id,
                agent_id=agent_id,
                status="active",
                claimed_at=ts,
            )
            return OwnershipResult(claim=claim, inserted=True, collision=False)

        self._conn.execute(
            """
            INSERT INTO ownership
                (resource_type, resource_id, agent_id, status, claimed_at, released_at)
            VALUES (?, ?, ?, 'active', ?, NULL)
            """,
            (resource_type, resource_id, agent_id, ts),
        )
        self._conn.commit()
        claim = OwnershipClaim(
            resource_type=resource_type,
            resource_id=resource_id,
            agent_id=agent_id,
            status="active",
            claimed_at=ts,
        )
        return OwnershipResult(claim=claim, inserted=True, collision=False)

    def release_ownership(
        self,
        *,
        resource_type: str,
        resource_id: str,
        agent_id: str,
    ) -> bool:
        row = self._conn.execute(
            """
            SELECT agent_id FROM ownership
            WHERE resource_type = ? AND resource_id = ? AND status = 'active'
            """,
            (resource_type, resource_id),
        ).fetchone()
        if row is None:
            return False
        if row["agent_id"] != agent_id:
            self._flag_collision(
                kind="ownership_release_denied",
                resource_type=resource_type,
                resource_id=resource_id,
                agent_id=agent_id,
                other_agent_id=row["agent_id"],
                detail=(
                    f"agent {agent_id!r} cannot release {resource_type}/{resource_id} "
                    f"held by {row['agent_id']!r}"
                ),
            )
            raise CollisionError(
                f"cannot release {resource_type}/{resource_id}: held by {row['agent_id']!r}",
                resource_type=resource_type,
                resource_id=resource_id,
                holder_agent_id=row["agent_id"],
                claimant_agent_id=agent_id,
            )
        ts = _utc_now()
        self._conn.execute(
            """
            UPDATE ownership
            SET status = 'released', released_at = ?
            WHERE resource_type = ? AND resource_id = ? AND status = 'active'
            """,
            (ts, resource_type, resource_id),
        )
        self._conn.commit()
        return True

    def get_owner(self, resource_type: str, resource_id: str) -> OwnershipClaim | None:
        row = self._conn.execute(
            """
            SELECT * FROM ownership
            WHERE resource_type = ? AND resource_id = ? AND status = 'active'
            """,
            (resource_type, resource_id),
        ).fetchone()
        if row is None:
            return None
        return OwnershipClaim(
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            agent_id=row["agent_id"],
            status=row["status"],
            claimed_at=row["claimed_at"],
            released_at=row["released_at"],
        )

    # --- send log ---

    def log_send(
        self,
        *,
        agent_id: str,
        channel: str,
        target: str,
        summary: str,
        idempotency_key: str | None = None,
    ) -> tuple[int, bool]:
        """Record who sent what. Returns (row_id, inserted).

        Duplicate ``idempotency_key`` is a no-op insert (returns existing id).
        """
        if not agent_id or not channel or not target or not summary:
            raise ValueError("agent_id, channel, target, summary are required")
        if idempotency_key:
            existing = self._conn.execute(
                "SELECT id FROM send_log WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                return int(existing["id"]), False
        ts = _utc_now()
        cur = self._conn.execute(
            """
            INSERT INTO send_log
                (agent_id, channel, target, summary, idempotency_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent_id, channel, target, summary, idempotency_key, ts),
        )
        self._conn.commit()
        return int(cur.lastrowid), True

    def list_sends(self, *, agent_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if agent_id:
            rows = self._conn.execute(
                """
                SELECT * FROM send_log WHERE agent_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (agent_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM send_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- collision flags ---

    def _flag_collision(
        self,
        *,
        kind: str,
        resource_type: str | None,
        resource_id: str | None,
        agent_id: str | None,
        other_agent_id: str | None,
        detail: str,
    ) -> int:
        ts = _utc_now()
        cur = self._conn.execute(
            """
            INSERT INTO collision_flags
                (kind, resource_type, resource_id, agent_id, other_agent_id, detail, created_at, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (kind, resource_type, resource_id, agent_id, other_agent_id, detail, ts),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_collisions(self, *, unresolved_only: bool = True) -> list[dict[str, Any]]:
        if unresolved_only:
            rows = self._conn.execute(
                "SELECT * FROM collision_flags WHERE resolved = 0 ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM collision_flags ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def resolve_collision(self, flag_id: int) -> bool:
        cur = self._conn.execute(
            "UPDATE collision_flags SET resolved = 1 WHERE id = ?",
            (flag_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0
