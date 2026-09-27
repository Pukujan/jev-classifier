"""Offline tests for the read-only ready-set derivation (#60 Stage 1).

Pure functions over snapshot dicts + a fixture scenario; no network, no gh.
Fixtures under tests/fixtures/ready/ mirror the real board states that
caused dispatch confusion today (#37 double-adjudication, #29 accepted but
unclaimed, #23 blocked on #21).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "coord_ready.py"
FIXDIR = REPO_ROOT / "tests" / "fixtures" / "ready"

_spec = importlib.util.spec_from_file_location("coord_ready", str(SCRIPT))
cr = importlib.util.module_from_spec(_spec)
sys.modules["coord_ready"] = cr
_spec.loader.exec_module(cr)


class TestDepParsing:
    def test_only_dependency_lines_count(self):
        body = (
            "Parent: #21\n"
            "Depends on: #29, #37\n"
            "Related: #6 is irrelevant lineage\n"
        )
        assert cr.dep_issue_numbers(body) == [29, 37]

    def test_none_dependency(self):
        assert cr.dep_issue_numbers("Dependencies: none") == []

    def test_blocked_by_label(self):
        assert cr.dep_issue_numbers("- Blocked by: #21 (#14 parent)") == [21]


class TestClassification:
    def _state(self, comments):
        return cr.R.fold([cr.to_fold_comment(c) for c in comments])

    def test_accepted_issue_level_ratify_is_ready(self):
        state = self._state([{
            "id": 1, "created_at": "2026-09-26T22:30:00Z",
            "user": {"login": "Pukujan"},
            "issue_url": "https://api.github.com/repos/o/r/issues/9",
            "body": "<!-- coord:verdict by=claude-code-main issue=9 decision=ACCEPT -->",
        }])
        issues = [{"number": 9, "state": "open", "title": "t", "body": "x"}]
        rs = cr.ready_set(issues, state)
        assert [e["number"] for e in rs["READY"]] == [9]

    def test_open_proposal_without_verdict_needs_adjudication(self):
        state = self._state([{
            "id": 2, "created_at": "2026-09-26T22:30:00Z",
            "user": {"login": "Pukujan"},
            "issue_url": "https://api.github.com/repos/o/r/issues/9",
            "body": "<!-- coord:proposal id=P-9-1 author=a issue=9 status=open -->",
        }])
        issues = [{"number": 9, "state": "open", "title": "t", "body": "x"}]
        rs = cr.ready_set(issues, state)
        assert [e["number"] for e in rs["NEEDS-VERDICT"]] == [9]

    def test_claimed_and_blocked(self):
        state = self._state([
            {"id": 3, "created_at": "2026-09-26T22:30:00Z", "user": {"login": "Pukujan"},
             "issue_url": "https://api.github.com/repos/o/r/issues/37",
             "body": "<!-- coord:claim issue=37 agent=x@y branch=feat/a-37 -->"},
        ])
        issues = [
            {"number": 37, "state": "open", "title": "ref graph", "body": "Parent: #21"},
            {"number": 23, "state": "open", "title": "study", "body": "Depends on: #21"},
            {"number": 21, "state": "open", "title": "program", "body": "Depends: none"},
        ]
        rs = cr.ready_set(issues, state)
        assert [e["number"] for e in rs["CLAIMED"]] == [37]
        assert [e["number"] for e in rs["BLOCKED-DEPS"]] == [23]
        assert [e["number"] for e in rs["READY"]] == [21]

    def test_closed_dependency_unblocks(self):
        state = self._state([])
        issues = [
            {"number": 60, "state": "open", "title": "dag", "body": "Depends: #22"},
            {"number": 22, "state": "closed", "title": "layer", "body": ""},
        ]
        rs = cr.ready_set(issues, state)
        assert [e["number"] for e in rs["READY"]] == [60]

    def test_unknown_dependency_fails_closed(self):
        state = self._state([])
        issues = [{"number": 5, "state": "open", "title": "t", "body": "Depends on: #999"}]
        rs = cr.ready_set(issues, state)
        # #999 not in the snapshot at all -> unverifiable -> BLOCKED, never READY
        assert [e["number"] for e in rs["BLOCKED-DEPS"]] == [5]
class TestFixturesAndCLI:
    def test_offline_fixture_scenario(self):
        out = subprocess.run([sys.executable, str(SCRIPT), "--fixtures", str(FIXDIR)],
                             capture_output=True, text=True)
        assert out.returncode == 0
        text = out.stdout
        assert "#29" in text.split("NEEDS-VERDICT")[0], "fixture: #29 must be READY"
        assert "#37" in text.split("CLAIMED")[1].split("BLOCKED")[0], "fixture: #37 CLAIMED"
        assert "#23" in text.split("BLOCKED-DEPS")[1], "fixture: #23 blocked on open #21"

    def test_prs_are_never_claimable_leaves(self):
        # GitHub's /issues endpoint also returns PRs; they carry a
        # pull_request key and must never appear as dispatch candidates.
        state = cr.R.fold([])
        issues = [
            {"number": 49, "state": "open", "title": "docs PR", "body": "x",
             "pull_request": {"html_url": "https://example.invalid/pull/49"}},
            {"number": 50, "state": "open", "title": "real leaf", "body": "Depends: none"},
        ]
        rs = cr.ready_set(issues, state)
        nums = [e["number"]
                for b in ("READY", "NEEDS-VERDICT", "CLAIMED", "BLOCKED-DEPS")
                for e in rs[b]]
        assert nums == [50], "a PR must not appear in any bucket"
        assert sum(rs["counts"].values()) == 1

    def test_json_output_has_readonly_and_snapshot_fields(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--fixtures", str(FIXDIR), "--json"],
            capture_output=True, text=True)
        d = json.loads(out.stdout)
        assert d["read_only"] is True and d["snapshot_utc"] == "offline"
        assert set(d["counts"]) == {"READY", "NEEDS-VERDICT", "CLAIMED", "BLOCKED-DEPS"}
        assert sum(d["counts"].values()) == 6, "fixture has 6 open issues"

    def test_missing_fixtures_dir_fails_clean(self, tmp_path):
        out = subprocess.run([sys.executable, str(SCRIPT), "--fixtures",
                              str(tmp_path / "nope")], capture_output=True, text=True)
        assert out.returncode == 2
        assert "coord_ready:" in out.stderr

    def test_max_age_flag_accepted_when_fresh(self):
        # offline elapsed is 0.0, so any positive cap passes; the refuse path
        # (fetch slower than --max-age-s -> exit 3) is live-only clock behavior
        assert cr.main(["--fixtures", str(FIXDIR), "--max-age-s", "1"]) == 0
