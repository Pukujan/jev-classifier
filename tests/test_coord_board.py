"""Offline tests for coordination layer v2 (#22): records parser + board gate.

No live API, no gh, no network: parsing is pure (records.py); the board CLI is
exercised through --comments-file fixtures. REST-shaped comment items mimic
`gh api repos/.../issues/comments` output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import coord_board  # noqa: E402
from jev_classifier.coord import records as R  # noqa: E402


def rest(body: str, cid: int, ts: str, issue: int = 22, login: str = "Pukujan") -> dict:
    return {
        "id": cid,
        "body": body,
        "created_at": ts,
        "user": {"login": login},
        "issue_url": f"https://api.github.com/repos/o/r/issues/{issue}",
    }


def comments_file(tmp_path: Path, items: list[dict]) -> str:
    p = tmp_path / "comments.json"
    p.write_text(json.dumps(items), encoding="utf-8")
    return str(p)


class TestRecordsParser:
    def test_coord_claim_roundtrip(self):
        recs = R.parse_comment(
            "<!-- coord:claim issue=22 agent=claude-code-main branch=feat/x-22 sha=deadbeef state=active -->",
            author="Pukujan", created_at="2026-09-26T19:00:00Z", issue=22, comment_id=1,
        )
        assert len(recs) == 1
        assert recs[0].attrs["branch"] == "feat/x-22"
        assert recs[0].marker == "coord"

    def test_claim_without_branch_is_malformed(self):
        try:
            R.parse_comment("<!-- coord:claim issue=5 agent=x -->",
                            author="a", created_at="", issue=5, comment_id=9)
            raise AssertionError("expected RecordError")
        except R.RecordError as exc:
            assert "branch" in str(exc)

    def test_fenced_examples_never_count(self):
        body = "protocol:\n```markdown\n<!-- coord:claim issue=99 agent=e branch=x-99 -->\n```\n"
        assert R.parse_comment(body, author="a", created_at="", issue=99, comment_id=2) == []

    def test_prose_claim_legacy(self):
        recs = R.parse_comment(
            "## Claim\n- Leaf: #15\n- Primary writer: Codex project agent\n- Branch: `feat/grok-source-bot`",
            author="Pukujan", created_at="2026-09-26T18:57:46Z", issue=15, comment_id=3,
        )
        assert len(recs) == 1 and recs[0].marker == "prose"
        assert recs[0].attrs["branch"] == "feat/grok-source-bot"
        assert "Codex" in recs[0].attrs["agent"]

    def test_two_agents_one_issue_collision_visible(self):
        st = R.fold([
            {"body": "<!-- coord:claim issue=7 agent=a@l branch=feat/a-7 -->", "author": "x",
             "created_at": "2026-09-26T19:00:00Z", "issue": 7, "comment_id": 1},
            {"body": "<!-- coord:claim issue=7 agent=b@c branch=feat/b-7 -->", "author": "x",
             "created_at": "2026-09-26T19:01:00Z", "issue": 7, "comment_id": 2},
        ])
        assert len(st.claim_for_issue(7)) == 2
        assert 7 in st.collisions()

    def test_ref_issue_number_convention(self):
        assert R.ref_issue_number("feat/coordination-layer-22") == 22
        assert R.ref_issue_number("feat/issue-9") == 9
        assert R.ref_issue_number("feat/bias-question-packs") is None


class TestLiveArbiterGrammar:
    """The real verdicts on #22 use issue=N decision=ACCEPT (no on=)."""

    ITEMS = [
        rest("<!-- coord:proposal id=P-22-1 author=coordination-flagger issue=22 "
             "status=open scope=coordination -->\n## Proposal P-22-1",
             1, "2026-09-26T19:10:00Z", issue=22),
        rest("<!-- coord:verdict by=claude-code-main issue=22 decision=ACCEPT -->",
             2, "2026-09-26T19:26:45Z", issue=22),
    ]

    def test_issue_level_ratify_unblocks_build(self, tmp_path):
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, self.ITEMS),
            "--proposal", "P-22-1", "--can-build", "--no-refs",
        ])
        assert rc == 0

    def test_uppercase_decision_normalized(self):
        st = R.fold([
            {"body": i["body"], "author": i["user"]["login"], "created_at": i["created_at"],
             "issue": 22, "comment_id": i["id"]} for i in self.ITEMS
        ])
        assert st.applied_verdicts["issue:22"].attrs["decision"] == "accepted"
        assert st.decision("P-22-1") == "accepted"
        assert not st.open_proposals()

    def test_session_id_verdict_is_authoritative_by_role(self):
        # Roster holds roles; live by= ids are per-session (role@device).
        st = R.fold([
            {"body": "<!-- coord:verdict on=P-9 by=claude-code-main@mbp14 decision=accepted -->",
             "author": "x", "created_at": "2026-09-26T20:00:00Z", "issue": 9, "comment_id": 1},
        ])
        assert "P-9" in st.applied_verdicts
        assert st.applied_verdicts["P-9"].attrs["by"] == "claude-code-main@mbp14"


class TestAdjudication:
    def _comments(self):
        return [
            rest("<!-- coord:proposal id=P-1 author=a@l issue=1 status=open -->\n## Proposal P-1",
                 1, "2026-09-26T18:00:00Z", issue=1),
            rest("<!-- coord:verdict on=P-1 by=claude-code-main decision=accepted -->",
                 2, "2026-09-26T19:00:00Z", issue=1),
        ]

    def test_accepted_verdict_unblocks_build(self, tmp_path):
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, self._comments()),
            "--proposal", "P-1", "--can-build", "--no-refs",
        ])
        assert rc == 0

    def test_open_proposal_blocks_build(self, tmp_path):
        items = self._comments()[:1]
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, items),
            "--proposal", "P-1", "--can-build", "--no-refs",
        ])
        assert rc == 3

    def test_later_advisory_rejection_cannot_void_accepted(self, tmp_path):
        items = self._comments() + [
            rest("<!-- coord:verdict on=P-1 by=rogue@x decision=rejected -->",
                 3, "2026-09-26T20:00:00Z", issue=1),
        ]
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, items),
            "--proposal", "P-1", "--can-build", "--no-refs",
        ])
        assert rc == 0, "advisory verdict must not change the applied decision"


class TestReceipts:
    BLANKET = ("<!-- coord:receipt run=2026-09-26T19-r1 task=JEV-0001 pr=29 "
               "commit=abc1234 outcome=merged started=2026-09-26T19:00Z "
               "finished=2026-09-26T19:40Z agent_alias=A-7f3c model_alias=M-91ab "
               "model_version_alias=V-04ef temperature=unavailable "
               "provenance=agent_declared -->")

    def test_receipt_folds_and_rejects_minless(self):
        recs = R.parse_comment(self.BLANKET, author="x",
                               created_at="2026-09-26T19:41:00Z", issue=22, comment_id=5)
        assert len(recs) == 1 and recs[0].rtype == "receipt"
        assert recs[0].key == "2026-09-26T19-r1"
        # blanket provenance: every field inherits agent_declared
        assert R.provenance_for(recs[0].attrs, "temperature") == "agent_declared"
        try:
            R.parse_comment("<!-- coord:receipt run=r2 -->", author="x",
                            created_at="", issue=1, comment_id=6)
            raise AssertionError("expected RecordError for missing outcome")
        except R.RecordError as exc:
            assert "outcome" in str(exc)

    def test_per_field_provenance_and_unknown_source_rejected(self):
        recs = R.parse_comment(
            "<!-- coord:receipt run=r-2 outcome=green "
            'tools="gh,pytest x4" temperature=0.2 '
            "provenance=outcome:runtime_observed;temperature:provider_returned;"
            "tools:agent_declared -->",
            author="x", created_at="", issue=23, comment_id=7,
        )
        a = recs[0].attrs
        assert R.provenance_for(a, "outcome") == "runtime_observed"
        assert R.provenance_for(a, "temperature") == "provider_returned"
        assert R.provenance_for(a, "tools") == "agent_declared"
        # a field with no token at all: unavailable, never guessed
        assert R.provenance_for(a, "commit") == "unavailable"
        try:
            R.parse_comment(
                "<!-- coord:receipt run=r-3 outcome=green "
                "provenance=outcome:bogus_source -->",
                author="x", created_at="", issue=23, comment_id=8)
            raise AssertionError("expected RecordError for unknown provenance")
        except R.RecordError as exc:
            assert "bogus_source" in str(exc)

    def test_board_shows_receipts_with_sources(self, tmp_path, capsys):
        items = [rest(
            "<!-- coord:receipt run=r-1 task=JEV-0002 outcome=green "
            "agent_alias=A-1 provenance=agent_alias:owner_recorded;"
            "outcome:runtime_observed -->",
            1, "2026-09-26T19:50:00Z", issue=23)]
        rc = coord_board.main(["--comments-file", comments_file(tmp_path, items), "--no-refs"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "RUN r-1" in out
        assert "A-1[owner_recorded]" in out
        assert "green[runtime_observed]" in out
        # field nobody sourced shows unavailable, not a guess
        assert "temp=—[unavailable]" in out


class TestIssueGate:
    def test_free_issue_allows_claim(self, tmp_path, capsys):
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, []),
            "--issue-open", "42", "--agent", "me@dev", "--no-refs",
        ])
        out = capsys.readouterr().out
        assert rc == 0 and "FREE issue=42" in out

    def test_prose_claimed_issue_blocks_other_agent(self, tmp_path, capsys):
        items = [rest("## Claim\n- Branch: `feat/grok-source-bot`\n- Primary writer: Codex project agent",
                      1, "2026-09-26T18:57:46Z", issue=15)]
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, items),
            "--issue-open", "15", "--agent", "claude-code-main", "--no-refs",
        ])
        out = capsys.readouterr().out
        assert rc == 3, "gate must see legacy prose claims"
        assert "CLAIMED issue=15" in out and "feat/grok-source-bot" in out

    def test_own_claim_returns_claimed_by_you(self, tmp_path, capsys):
        items = [rest("<!-- coord:claim issue=15 agent=claude-code-main branch=feat/g-15 -->",
                      1, "2026-09-26T18:57:46Z", issue=15)]
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, items),
            "--issue-open", "15", "--agent", "claude-code-main", "--no-refs",
        ])
        out = capsys.readouterr().out
        assert rc == 0 and "CLAIMED-BY-YOU issue=15" in out

    def test_closed_issue_blocks(self, tmp_path, capsys):
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, []),
            "--issue-open", "6", "--agent", "me@dev", "--no-refs",
            "--issue-state", "closed",
        ])
        out = capsys.readouterr().out
        assert rc == 3 and "CLOSED issue=6" in out

    def test_board_renders_live_records(self, tmp_path, capsys):
        items = [
            rest("<!-- coord:proposal id=P-1 author=a@l issue=1 status=open -->\n## P-1",
                 1, "2026-09-26T18:00:00Z", issue=1),
            rest("<!-- coord:claim issue=3 agent=b@l branch=feat/x-3 -->",
                 2, "2026-09-26T18:30:00Z", issue=3),
            rest("<!-- coord:claim issue=4 agent=c@l -->",  # malformed: no branch
                 3, "2026-09-26T18:40:00Z", issue=4),
        ]
        rc = coord_board.main(["--comments-file", comments_file(tmp_path, items), "--no-refs"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "P-1" in out and "OPEN" in out
        assert "agent=b@l" in out and "branch=feat/x-3" in out
        assert "MALFORMED" in out and "branch" in out

    def test_ref_without_claim_flagged(self, tmp_path, capsys):
        """Reserved ref exists on origin but its claim comment was lost."""
        state_items = []  # no claim comments at all
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, state_items),
        ])
        # refs only resolve live; offline comments-file mode has refs=[] so the
        # orphan check is silent here — assert via direct render instead:
        out = capsys.readouterr().out
        assert rc == 0
        text = coord_board.render(*_state_with_ref())
        assert "REF-WITHOUT-CLAIM" in text and "issue=31" in text


def _state_with_ref():
    """(state, refs, merged) with a live reserved ref and no claim comment."""
    st = R.fold([
        {"body": "<!-- coord:claim issue=8 agent=z@l branch=feat/other-8 -->",
         "author": "x", "created_at": "2026-09-26T19:00:00Z", "issue": 8, "comment_id": 1},
    ])
    return st, ["feat/lost-claim-31", "feat/other-8"], set()


class TestNoPostTrap:
    def test_gh_get_always_explicit_get(self, monkeypatch):
        """gh api silently POSTs when -f fields are present; every call must pin -X GET."""
        calls: list[list[str]] = []

        def fake_run(cmd, timeout=120):
            calls.append(list(cmd))
            return "[]"

        monkeypatch.setattr(coord_board, "_run", fake_run)
        coord_board.gh_get("repos/o/r/issues/comments", "per_page=100", paginate=True)
        cmd = calls[0]
        assert "-X" in cmd and "GET" in cmd, cmd
        assert "-f" in cmd  # field present but method pinned


class TestSettleAndIdentity:
    def test_closed_issue_settles_stale_claim(self):
        st = R.fold([
            {"body": "<!-- coord:claim issue=6 agent=a@l branch=feat/x-6 -->",
             "author": "x", "created_at": "2026-09-26T18:31:35Z", "issue": 6, "comment_id": 1},
            {"body": "<!-- coord:claim issue=22 agent=b@l branch=feat/y-22 -->",
             "author": "x", "created_at": "2026-09-26T19:00:00Z", "issue": 22, "comment_id": 2},
        ])
        assert len(st.live_claims()) == 2
        R.settle_claims(st, closed_issues=[6], merged_branches=["feat/y-22"])
        assert st.live_claims() == []
        by = {c.key: c.attrs.get("released_by") for c in st.all_claims}
        assert by["6"] == "closed_issue" and by["22"] == "merged_pr"

    def test_agent_matches_session_tolerance(self):
        # bare role matches role@device (claim comments omit the suffix)
        assert R.agent_matches("coordination-flagger", "coordination-flagger@mbp14")
        assert R.agent_matches("coordination-flagger@mbp14", "coordination-flagger")
        # exact equality always matches
        assert R.agent_matches("a@x", "a@x")
        # two DIFFERENT declared sessions never match: the #22 collision case
        assert not R.agent_matches("claude-code-main@mbp1", "claude-code-main@mbp2")
        assert not R.agent_matches("a@x", "b@x")
        assert not R.agent_matches("", "a")

    def test_gate_claimed_by_you_with_session_suffix(self, tmp_path, capsys):
        items = [rest("<!-- coord:claim issue=22 agent=coordination-flagger "
                      "branch=feat/coordination-layer-22 -->",
                      1, "2026-09-26T19:09:12Z", issue=22)]
        rc = coord_board.main([
            "--comments-file", comments_file(tmp_path, items),
            "--issue-open", "22", "--agent", "coordination-flagger@mbp14", "--no-refs",
        ])
        out = capsys.readouterr().out
        assert rc == 0 and "CLAIMED-BY-YOU" in out
