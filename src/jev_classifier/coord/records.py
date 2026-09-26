"""Coordination record parsing: `coord:*` HTML-comment markers plus legacy prose claims.

Single source of truth for the machine-readable layer of the agent coordination
protocol (docs/AGENT_COORD.md, docs/AGENT_PROPOSALS.md). Four record types are
carried in GitHub issue comments:

  coord:proposal  design option awaiting adjudication   (id, author, issue, scope, status, depends)
  coord:verdict   adjudication of one proposal          (on|proposal|issue, by, decision)
  coord:claim     reservation to build one issue        (issue, agent, branch, sha, state)
  coord:receipt   append-only run receipt (#22 owner telemetry direction)
                  (run, outcome, task, pr, commit, started, finished, agent_alias,
                   model_alias, model_version_alias, temperature, provenance)

Plus a legacy/fallback path: agents already claim with prose (`## Claim` heading
with a `Branch:` line). Those are parsed into synthetic claim records tagged
`marker=prose` so the board sees them too; the machine marker remains the
preferred form.

Terminology: a `coord:claim` is a WORK LOCK on a GitHub issue. It is unrelated
to the epistemic claim records in docs/CLAIM_SCHEMA.md (paper claims with
valid/recorded time). Same word, different layer.

Authority note: `by=` and `agent=` are self-declared under a single shared
GitHub account, so they are evidence, not enforcement. The ledger only *applies*
verdicts whose `by=` is in AUTHORITATIVE_AGENTS; everything else is advisory and
can never void an accepted decision.

This module is pure parsing + folding: no network, no subprocess, deterministic.
"""

from __future__ import annotations
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

MARKER_RE = re.compile(r"<!--\s*coord:(\w+)\s+(.*?)\s*-->", re.DOTALL)
ATTR_RE = re.compile(r'(\w+)=("([^"]*)"|\S+)')
RECORD_TYPES = ("proposal", "verdict", "claim", "receipt")

# Verdicts with by= outside this roster are advisory. Roster entries are
# ROLES: live ids are per-session (`role@device`), so is_authoritative matches
# the role before the first @ (an exact full-id entry also pins one machine).
# Update only via an owner-endorsed change to docs/AUTHORITY.md.
AUTHORITATIVE_AGENTS = frozenset({"claude-code-main"})

# Per-field provenance vocabulary (owner telemetry direction on #22): every
# recorded receipt field names its evidence class. A field without a source
# is reported `unavailable`; nothing may be inferred from defaults.
PROVENANCE_VOCAB = frozenset({
    "runtime_observed",    # seen in our own code/logs at run time
    "provider_returned",   # surfaced by the model/provider response
    "agent_declared",      # the writing agent attests it (weak signal)
    "owner_recorded",      # entered by the human owner
    "unavailable",         # explicitly unknown
})

# Canonical decision vocabulary. The live arbiter writes prose-style rulings
# (ACCEPT / REJECT / DEFER on #22); both spellings must fold to one state, or
# an accepted proposal still reads "open" and --can-build refuses real work.
DECISION_SYNONYMS = {
    "accept": "accepted", "accepted": "accepted", "go": "accepted",
    "reject": "rejected", "rejected": "rejected",
    "supersede": "superseded", "superseded": "superseded",
    "defer": "deferred", "deferred": "deferred",
}


def normalize_decision(raw: str) -> str:
    """Canonical form of a verdict decision token.

    Exact synonyms win; otherwise normalize by prefix so the project's
    compound rulings (ACCEPT-DECOMPOSE, #21; ACCEPT-DEFERRED, #23) fold to
    the same states the gate understands. Unknown values pass through
    lowercased (advisory display), never silently coerced.
    """
    low = (raw or "").strip().lower()
    if low in DECISION_SYNONYMS:
        return DECISION_SYNONYMS[low]
    for prefix, canonical in (("accept", "accepted"), ("reject", "rejected"),
                              ("defer", "deferred"), ("supersed", "superseded")):
        if low.startswith(prefix):
            return canonical
    return low

# Records inside fenced code blocks are documentation examples, not state.
FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)

# Legacy prose claims: a comment with a `## Claim`/`## Claiming` heading and a
# `Branch: <ref>` line (optionally backticked) plus an optional writer/agent line.
PROSE_CLAIM_HEADING_RE = re.compile(r"(?im)^\s*#+\s*claim(?:ing|s)?\b")
PROSE_BRANCH_RE = re.compile(r"(?im)^\s*[-*]?\s*branch\s*[:=]\s*`?([A-Za-z0-9._/-]+)`?")
PROSE_WRITER_RE = re.compile(
    r"(?im)^\s*[-*]?\s*(?:primary writer|claimant|writer|agent)\s*[:=]\s*`?([^`\n]+?)`?\s*(?:\(|$)"
)
PROSE_RELEASED_RE = re.compile(
    r"(?i)\bstate\s*[:=]\s*released\b|\breleas(?:e|ed) the claim\b|^\s*#+\s*releas",
    re.MULTILINE,
)

# Reserved-branch convention: the final path segment ends with the issue number,
# e.g. feat/coordination-layer-22, feat/issue-22, hotfix/22.
REF_ISSUE_RE = re.compile(r"(?:^|[-/])(?:issue-)?(\d+)$")


class RecordError(ValueError):
    """A coordination record is malformed beyond repair."""


@dataclass(frozen=True)
class Record:
    rtype: str
    attrs: dict[str, str]
    author: str            # GitHub login that posted it (shared account: weak signal)
    created_at: str
    issue: int             # issue the comment lives on
    comment_id: int
    marker: str = "coord"  # "coord" (HTML marker) or "prose" (## Claim heading)

    @property
    def key(self) -> str:
        if self.rtype == "proposal":
            return self.attrs.get("id", "")
        if self.rtype == "verdict":
            # Proposal-targeted verdicts key by proposal id; issue-level
            # ratifications (live arbiter grammar: issue=22 decision=ACCEPT)
            # key namespaced so they can never collide with a proposal id.
            target = self.attrs.get("on") or self.attrs.get("proposal")
            if target:
                return target
            return f"issue:{self.attrs.get('issue') or self.issue}"
        if self.rtype == "receipt":
            return self.attrs.get("run", "")
        return self.attrs.get("issue", "")

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.rtype,
            "marker": self.marker,
            "attrs": dict(sorted(self.attrs.items())),
            "author": self.author,
            "created_at": self.created_at,
            "issue": self.issue,
            "comment_id": self.comment_id,
        }


def parse_attrs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in ATTR_RE.finditer(raw):
        out[match.group(1)] = match.group(3) if match.group(3) is not None else match.group(2)
    return out


def looks_like_claim_heading(body: str) -> bool:
    return bool(PROSE_CLAIM_HEADING_RE.search(body))


def parse_prose_claim(
    body: str,
    *,
    author: str,
    created_at: str,
    issue: int,
    comment_id: int,
) -> Record | None:
    """Synthesize a claim record from a `## Claim` prose comment, if parseable.

    Returns None (not an error) when the heading exists but no `Branch:` line:
    half-claiming in prose is common and must not poison the whole comment.
    """
    if not PROSE_CLAIM_HEADING_RE.search(body):
        return None
    branch_match = PROSE_BRANCH_RE.search(body)
    if not branch_match:
        return None
    agent = author
    writer_match = PROSE_WRITER_RE.search(body)
    if writer_match:
        agent = writer_match.group(1).strip()
    attrs = {"issue": str(issue), "agent": agent, "branch": branch_match.group(1)}
    sha_match = re.search(r"(?im)^\s*[-*]?\s*sha\s*[:=]\s*`?([0-9a-f]{7,40})`?", body)
    if sha_match:
        attrs["sha"] = sha_match.group(1)
    if PROSE_RELEASED_RE.search(body):
        attrs["state"] = "released"
    return Record(rtype="claim", attrs=attrs, author=author, created_at=created_at,
                  issue=issue, comment_id=comment_id, marker="prose")


def parse_comment(
    body: str,
    *,
    author: str,
    created_at: str,
    issue: int,
    comment_id: int,
) -> list[Record]:
    """Extract coordination records from one comment body.

    Fenced examples are stripped first so protocol docs pasted into a comment
    cannot fabricate claims or verdicts. Raises RecordError on coord markers
    missing required identity fields (a half-parsed marker is worse than none);
    prose claims degrade to no-record instead.

    Verdict grammar tolerance (live arbiter usage on #22): the target may be
    given as on= / proposal= / issue=, and decision arrives uppercase (ACCEPT);
    decisions are lowercased here, targeting is resolved in Record.key.
    """
    stripped = FENCE_RE.sub("", body or "")
    records: list[Record] = []
    for match in MARKER_RE.finditer(stripped):
        rtype, raw_attrs = match.group(1), match.group(2)
        if rtype not in RECORD_TYPES:
            continue
        attrs = parse_attrs(" ".join(raw_attrs.split()))
        if rtype == "verdict":
            if not {"on", "proposal", "issue"} & set(attrs):
                raise RecordError(f"coord:verdict missing on= (comment {comment_id})")
            if "decision" not in attrs:
                raise RecordError(f"coord:verdict missing decision= (comment {comment_id})")
            attrs["decision_raw"] = attrs["decision"]
            attrs["decision"] = normalize_decision(attrs["decision"])
        elif rtype == "receipt":
            # Append-only run receipt (owner telemetry direction on #22).
            # Required: run (stable id) + outcome. Aliases are opaque; the
            # alias->identity map stays owner-side, never in this repo.
            if "run" not in attrs or "outcome" not in attrs:
                raise RecordError(
                    f"coord:receipt missing run=/outcome= (comment {comment_id})"
                )
            # Per-field provenance: `provenance=model:provider_returned;
            # temperature:unavailable`, or one blanket token. Unknown sources
            # are rejected so a typo cannot smuggle an unlabeled field in.
            for token in re.split(r"[;,\s]+", attrs.get("provenance", "")):
                if not token:
                    continue
                source = token.rpartition(":")[2]
                if source not in PROVENANCE_VOCAB:
                    raise RecordError(
                        f"coord:receipt provenance '{token}' not in "
                        f"{sorted(PROVENANCE_VOCAB)} (comment {comment_id})"
                    )
        else:
            required = {"proposal": "id", "claim": "issue"}[rtype]
            if required not in attrs:
                raise RecordError(f"coord:{rtype} missing {required}= (comment {comment_id})")
            if rtype == "claim" and "branch" not in attrs:
                raise RecordError(
                    f"coord:claim missing branch= (comment {comment_id}); "
                    "a claim without a reserved ref is not a lock"
                )
        records.append(
            Record(rtype=rtype, attrs=attrs, author=author, created_at=created_at,
                   issue=issue, comment_id=comment_id, marker="coord")
        )
    if not records and looks_like_claim_heading(stripped):
        rec = parse_prose_claim(stripped, author=author, created_at=created_at,
                                issue=issue, comment_id=comment_id)
        if rec is not None:
            records.append(rec)
    return records


def ref_issue_number(ref: str) -> int | None:
    """Issue number encoded in a reserved branch name, or None."""
    match = REF_ISSUE_RE.search(ref.split("/")[-1])
    return int(match.group(1)) if match else None


@dataclass
class CoordState:
    """Folded current coordination state for a repo."""
    proposals: dict[str, Record] = field(default_factory=dict)          # proposal id -> latest
    applied_verdicts: dict[str, Record] = field(default_factory=dict)   # key -> authoritative verdict
    advisory_verdicts: dict[str, list[Record]] = field(default_factory=dict)
    claims: dict[tuple[str, str], Record] = field(default_factory=dict)  # (issue, who) -> latest
    receipts: dict[str, Record] = field(default_factory=dict)            # run id -> latest
    malformed: list[tuple[int, int, str]] = field(default_factory=list)  # issue, comment_id, error

    @property
    def all_claims(self) -> list[Record]:
        return list(self.claims.values())

    def decision(self, proposal_id: str) -> str:
        verdict = self.applied_verdicts.get(proposal_id)
        if verdict is None:
            # Issue-level ratification (`issue:N`): it applies to proposals
            # carrying the same issue=, keyed namespaced so it can never join
            # or clobber a proposal-targeted verdict.
            p = self.proposals.get(proposal_id)
            issue = p.attrs.get("issue", "") if p else ""
            if issue:
                verdict = self.applied_verdicts.get(f"issue:{issue}")
        return verdict.attrs["decision"] if verdict else "open"

    def issue_ratified(self, issue: int) -> str:
        """Decision of an issue-level ratification comment, or 'none'."""
        verdict = self.applied_verdicts.get(f"issue:{issue}")
        return verdict.attrs["decision"] if verdict else "none"

    def live_claims(self) -> list[Record]:
        return [c for c in self.all_claims if c.attrs.get("state") != "released"]

    def claim_for_issue(self, issue: int) -> list[Record]:
        return [c for c in self.live_claims() if c.attrs.get("issue") == str(issue)]

    def released_branches(self, issue: int) -> set[str]:
        return {
            c.attrs.get("branch", "")
            for c in self.all_claims
            if c.attrs.get("issue") == str(issue) and c.attrs.get("state") == "released"
        }

    def collisions(self) -> dict[int, list[Record]]:
        """Issues with more than one live claim holding DIFFERENT locks.

        The reserved branch is the mutex: a ref cannot have two holders, and
        one agent posting a legacy prose claim plus a coord marker for the
        SAME branch is a double record, not a collision. The old agent+branch
        tuple rule flagged exactly that documented pattern (observed on #35)
        and would train agents to ignore the alarm. Holder = the branch when
        present, else the agent (branch-less rows). Collision fires only on
        more than one distinct holder per issue.
        """
        groups: dict[int, list[Record]] = {}
        for c in self.live_claims():
            try:
                n = int(c.attrs.get("issue", "0"))
            except ValueError:
                continue
            groups.setdefault(n, []).append(c)
        out: dict[int, list[Record]] = {}
        for n, cs in groups.items():
            holders = {
                c.attrs.get("branch") or f"agent:{c.attrs.get('agent', '?')}"
                for c in cs
            }
            if len(holders) > 1:
                out[n] = cs
        return out

    def open_proposals(self) -> list[Record]:
        out = []
        for pid, p in sorted(self.proposals.items()):
            if p.attrs.get("status") == "withdrawn":
                continue
            if self.decision(pid) in ("accepted", "rejected", "superseded"):
                continue
            out.append(p)
        return out


def is_authoritative(rec: Record, roster: frozenset[str] = AUTHORITATIVE_AGENTS) -> bool:
    by = rec.attrs.get("by", "")
    return by in roster or by.split("@", 1)[0] in roster


def agent_matches(a: str, b: str) -> bool:
    """Same actor? Full ids match exactly; a bare role matches `role@device`
    (the claim/comment may omit the session suffix). Two ids that both carry
    different @device suffixes are DIFFERENT sessions — that ambiguity is what
    caused the #22 double-`claude-code-main` collision, so it must not match.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    ra = a.split("@", 1)[0] if "@" in a else a
    rb = b.split("@", 1)[0] if "@" in b else b
    if "@" in a and "@" in b:
        return False  # both declare sessions; only exact equality counts
    return ra == rb


def settle_claims(
    state: CoordState,
    *,
    closed_issues: "Iterable[int] | None" = None,
    merged_branches: "Iterable[str] | None" = None,
) -> CoordState:
    """Release claim rows whose lock can no longer be real (in place).

    The docs promise that merging the PR (or closing the issue) releases the
    claim; a stale `## Claim` comment must not block a legitimately free issue
    forever. A row is settled to released when its reserved branch merged
    (PR-head truth) or its issue is closed (GitHub-state truth). Explicit
    `state=released` is already honored by live_claims(). Each settled row
    records `released_by` so the board stays auditable. Returns the same
    state for chaining.
    """
    closed = {str(n) for n in (closed_issues or ())}
    merged = set(merged_branches or ())
    for c in state.all_claims:
        if c.attrs.get("state") == "released":
            continue
        if c.attrs.get("branch", "") in merged:
            c.attrs["state"] = "released"
            c.attrs["released_by"] = "merged_pr"
        elif c.attrs.get("issue", "") in closed:
            c.attrs["state"] = "released"
            c.attrs["released_by"] = "closed_issue"
    return state

def provenance_for(attrs: dict[str, str], field: str) -> str:
    """Evidence class of one receipt field: per-field token wins, then a
    blanket token, else `unavailable` (never guessed)."""
    fallback = "unavailable"
    for token in re.split(r"[;,\s]+", attrs.get("provenance", "")):
        if not token:
            continue
        key, sep, src = token.rpartition(":")
        if sep and key == field:
            return src
        if not sep:
            fallback = src
    return fallback


def age_hours(rec: Record, now: datetime | None = None) -> float | None:
    try:
        stamp = datetime.fromisoformat((rec.created_at or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - stamp).total_seconds() / 3600.0


def fold(
    comments: list[dict],
    *,
    roster: frozenset[str] = AUTHORITATIVE_AGENTS,
) -> CoordState:
    """Fold raw comment dicts into current state.

    Each comment dict needs: body, author, created_at, issue, comment_id.
    Last-writer-wins per record id, with separate slots so a later
    non-roster (advisory) verdict can never displace an applied decision:

    - proposals: keyed by proposal id
    - verdicts:  authoritative per key (proposal id or namespaced issue:N);
                 advisory appended per key
    - claims:    keyed by (issue, holder). coord markers use the declared
                 agent; prose claims use the branch (every agent shares the
                 GitHub login, and the branch is the real mutex). Two agents
                 claiming one issue therefore keep two rows and collisions()
                 fires; the same holder re-claiming replaces its own row.
    - receipts:  keyed by run id; append-only stream folded to latest per run.
    """
    state = CoordState()
    ordered = sorted(comments, key=lambda c: (c.get("created_at", ""), int(c.get("comment_id", 0))))
    for c in ordered:
        try:
            records = parse_comment(
                c.get("body", ""),
                author=c.get("author", "?"),
                created_at=c.get("created_at", ""),
                issue=int(c.get("issue", 0)),
                comment_id=int(c.get("comment_id", 0)),
            )
        except RecordError as exc:
            state.malformed.append(
                (int(c.get("issue", 0)), int(c.get("comment_id", 0)), str(exc))
            )
            continue
        for rec in records:
            if rec.rtype == "proposal":
                state.proposals[rec.key] = rec
            elif rec.rtype == "verdict":
                if is_authoritative(rec, roster):
                    state.applied_verdicts[rec.key] = rec
                else:
                    state.advisory_verdicts.setdefault(rec.key, []).append(rec)
            elif rec.rtype == "claim":
                who = (rec.attrs.get("agent", "?") if rec.marker == "coord"
                       else rec.attrs.get("branch", "?"))
                state.claims[(rec.key, who)] = rec
            elif rec.rtype == "receipt":
                state.receipts[rec.key] = rec
    return state
