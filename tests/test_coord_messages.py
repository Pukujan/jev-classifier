"""Offline tests for coord:message grammar and the #61 post/read helper.

No network, no gh: parsing/dedup/id-generation and the dry-run render path
are pure; live read/post paths are exercised through monkeypatched
fetch_issue_comments so the at-least-once and authority boundaries are pinned.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from jev_classifier.coord import records as R  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "coord_messages", str(REPO_ROOT / "scripts" / "coord_messages.py"))
cm = importlib.util.module_from_spec(_spec)
sys.modules["coord_messages"] = cm
_spec.loader.exec_module(cm)


def cmt(body, cid=1, ts="2026-09-27T00:00:00Z", issue=61, login="Pukujan"):
    """Fold-ready comment dict (REST shape)."""
    return {"body": body, "author": login, "created_at": ts,
            "issue": issue, "comment_id": cid}


def msg(body, cid=1, ts="2026-09-27T00:00:00Z", issue=61):
    return R.fold([cmt(body, cid, ts, issue)]).messages


class TestMessageGrammar:
    def test_valid_message_roundtrip(self):
        recs = R.parse_comment(
            "<!-- coord:message id=m-1 task=JEV-61 from=a@x kind=request to=b@y -->\nbody",
            author="Pukujan", created_at="2026-09-27T00:00:00Z", issue=61, comment_id=1)
        assert recs[0].rtype == "message" and recs[0].key == "m-1"
        assert recs[0].attrs["kind"] == "request"

    def test_all_kinds_accepted(self):
        for kind in sorted(R.MESSAGE_KINDS):
            recs = R.parse_comment(
                f"<!-- coord:message id=m task=t from=a kind={kind} -->",
                author="x", created_at="", issue=1, comment_id=1)
            assert recs[0].attrs["kind"] == kind

    def test_unknown_kind_rejected(self):
        try:
            R.parse_comment("<!-- coord:message id=m task=t from=a kind=ping -->",
                            author="x", created_at="", issue=1, comment_id=1)
            raise AssertionError("expected RecordError")
        except R.RecordError as exc:
            assert "ping" in str(exc)

    def test_required_fields_enforced(self):
        for body, frag in [
            ("<!-- coord:message task=t from=a kind=ack -->", "id"),
            ("<!-- coord:message id=m from=a kind=ack -->", "task"),
            ("<!-- coord:message id=m task=t kind=ack -->", "from"),
        ]:
            try:
                R.parse_comment(body, author="x", created_at="", issue=1, comment_id=2)
                raise AssertionError(f"expected RecordError for {frag}")
            except R.RecordError as exc:
                assert frag in str(exc)

    def test_provenance_vocab_enforced(self):
        try:
            R.parse_comment("<!-- coord:message id=m task=t from=a kind=ack "
                            "provenance=from:fabricated -->",
                            author="x", created_at="", issue=1, comment_id=3)
            raise AssertionError("expected RecordError")
        except R.RecordError as exc:
            assert "fabricated" in str(exc)

    def test_fold_dedupes_by_id(self):
        st = R.fold([
            cmt("<!-- coord:message id=m-1 task=T from=a kind=status -->", 1,
                "2026-09-27T00:00:00Z"),
            cmt("<!-- coord:message id=m-1 task=T from=a kind=ack -->", 2,
                "2026-09-27T00:01:00Z"),
        ])
        assert len(st.messages) == 1
        assert st.messages["m-1"].attrs["kind"] == "ack", "latest wins per id"

    def test_message_never_authority(self):
        # a coord:message cannot adjudicate a proposal
        st = R.fold([
            cmt("<!-- coord:proposal id=P-1 author=a issue=1 status=open -->", 1,
                "2026-09-27T00:00:00Z"),
            cmt("<!-- coord:message id=m-1 task=t from=a kind=answer reply_to=P-1 -->", 2,
                "2026-09-27T00:01:00Z"),
        ])
        assert st.decision("P-1") == "open", "a message is not a verdict"


class TestMessageHelper:
    def test_default_message_id_is_stable(self):
        a = cm.default_message_id(61, "a@x", "hello")
        b = cm.default_message_id(61, "a@x", "hello")
        c = cm.default_message_id(61, "a@x", "hello!")
        assert a == b and a != c
        assert a.startswith("m-61-")

    def test_render_marker_parses_back(self):
        marker = cm.render_marker(msg_id="m-9", task="JEV-9", sender="a@x", kind="handoff",
                                  recipient="b@y", reply_to="m-1", thread="m-9", idem="m-9")
        body = marker + "\n\ntext"
        recs = R.parse_comment(body, author="x", created_at="t", issue=9, comment_id=1)
        assert recs[0].attrs["kind"] == "handoff"
        assert recs[0].attrs["reply_to"] == "m-1"
        assert recs[0].attrs["to"] == "b@y"

    def test_dry_run_posts_nothing(self, capsys):
        rc = cm.main(["post", "--issue", "61", "--from", "a@x", "--kind", "status",
                      "--message", "progress note", "--dry-run"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "coord:message id=m-61-" in out and "kind=status" in out

    def test_read_dedupes_and_orders(self, monkeypatch):
        # duplicate POSTS (same id) arrive as two comments; fetch returns the
        # REST shape read_messages itself folds
        dupes = [
            {"id": 1, "body": "<!-- coord:message id=m-1 task=T from=a kind=status -->",
             "created_at": "2026-09-27T00:00:00Z", "user": {"login": "u"},
             "issue_url": "https://api.github.com/repos/o/r/issues/61"},
            {"id": 2, "body": "<!-- coord:message id=m-1 task=T from=a kind=ack -->",
             "created_at": "2026-09-27T00:02:00Z", "user": {"login": "u"},
             "issue_url": "https://api.github.com/repos/o/r/issues/61"},
            {"id": 3, "body": "<!-- coord:message id=m-2 task=T from=b kind=request to=a@x -->",
             "created_at": "2026-09-27T00:01:00Z", "user": {"login": "u"},
             "issue_url": "https://api.github.com/repos/o/r/issues/61"},
        ]
        monkeypatch.setattr(cm, "fetch_issue_comments",
                            lambda repo, issue: [cm.to_fold_comment(d) for d in dupes])
        msgs = cm.read_messages("r", [61], kind=None, to_alias=None, thread=None)
        assert [(m.key, m.attrs.get("kind")) for m in msgs] == [
            ("m-2", "request"), ("m-1", "ack")]

    def test_read_filter_to_and_kind(self, monkeypatch):
        data = [
            cmt("<!-- coord:message id=m-1 task=T from=a kind=request to=b@y -->", 1),
            cmt("<!-- coord:message id=m-2 task=T from=a kind=ack to=c@z -->", 2),
        ]
        monkeypatch.setattr(cm, "fetch_issue_comments", lambda repo, issue: data)
        got = cm.read_messages("r", [61], kind="request", to_alias="b@y", thread=None)
        assert [m.key for m in got] == ["m-1"]
        assert cm.read_messages("r", [61], kind=None, to_alias="nobody@x", thread=None) == []

    def test_post_skips_idempotent_replay(self, monkeypatch, capsys):
        monkeypatch.setattr(cm, "fetch_issue_comments", lambda repo, issue: [
            cmt("<!-- coord:message id=m-1 task=T from=a@x kind=status -->", 1)])
        called = {"posted": False}

        def fake_gh(args, timeout=180):
            called["posted"] = True
            return "{}"
        monkeypatch.setattr(cm, "_gh", fake_gh)
        rc = cm.main(["post", "--issue", "61", "--from", "a@x", "--kind", "status",
                      "--message", "x", "--msg-id", "m-1"])
        out = capsys.readouterr().out
        assert rc == 0 and "idempotent replay skipped" in out
        assert called["posted"] is False, "must not double-post"

    def test_post_rejects_id_collision(self, monkeypatch, capsys):
        monkeypatch.setattr(cm, "fetch_issue_comments", lambda repo, issue: [
            cmt("<!-- coord:message id=m-1 task=T from=evil@x kind=ack -->", 1)])
        rc = cm.main(["post", "--issue", "61", "--from", "a@x", "--kind", "status",
                      "--message", "x", "--msg-id", "m-1"])
        err = capsys.readouterr().err
        assert rc == 3 and "collision" in err

    def test_check_finds_idem(self, monkeypatch, capsys):
        monkeypatch.setattr(cm, "fetch_issue_comments", lambda repo, issue: [
            cmt("<!-- coord:message id=m-5 task=T from=a kind=ack idem=key-9 -->", 1)])
        assert cm.main(["check", "--issue", "61", "--idem", "key-9"]) == 0
        assert cm.main(["check", "--issue", "61", "--idem", "absent"]) == 1
