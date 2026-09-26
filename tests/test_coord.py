"""Red-first tests for coord store: idempotent checkpoints + ownership collision."""

from __future__ import annotations

import pytest

from jev_classifier.coord import CollisionError, CoordStore


def test_checkpoint_insert_is_idempotent() -> None:
    with CoordStore(":memory:") as store:
        first = store.put_checkpoint(
            "issue-3/iter-0/schema",
            agent_id="agent-a",
            issue_number=3,
            payload_json='{"ok": true}',
        )
        assert first.inserted is True
        assert first.agent_id == "agent-a"

        second = store.put_checkpoint(
            "issue-3/iter-0/schema",
            agent_id="agent-b",  # different agent, same key
            issue_number=3,
            payload_json='{"ok": false}',
        )
        assert second.inserted is False
        assert second.checkpoint_key == first.checkpoint_key
        assert second.agent_id == "agent-a"  # original holder retained
        assert second.created_at == first.created_at

        row = store.get_checkpoint("issue-3/iter-0/schema")
        assert row is not None
        assert row["agent_id"] == "agent-a"
        assert row["payload_json"] == '{"ok": true}'


def test_ownership_claim_collision_raises_and_flags() -> None:
    with CoordStore(":memory:") as store:
        first = store.claim_ownership(
            resource_type="issue",
            resource_id="3",
            agent_id="agent-a",
        )
        assert first.inserted is True
        assert first.collision is False
        assert first.claim.agent_id == "agent-a"

        with pytest.raises(CollisionError) as ei:
            store.claim_ownership(
                resource_type="issue",
                resource_id="3",
                agent_id="agent-b",
            )
        assert ei.value.holder_agent_id == "agent-a"
        assert ei.value.claimant_agent_id == "agent-b"
        assert ei.value.resource_type == "issue"
        assert ei.value.resource_id == "3"

        flags = store.list_collisions(unresolved_only=True)
        assert len(flags) == 1
        assert flags[0]["kind"] == "ownership_collision"
        assert flags[0]["agent_id"] == "agent-b"
        assert flags[0]["other_agent_id"] == "agent-a"


def test_same_agent_reclaim_is_not_collision() -> None:
    with CoordStore(":memory:") as store:
        store.claim_ownership(resource_type="pr", resource_id="9", agent_id="agent-a")
        again = store.claim_ownership(
            resource_type="pr",
            resource_id="9",
            agent_id="agent-a",
        )
        assert again.inserted is False
        assert again.collision is False
        assert store.list_collisions() == []


def test_ownership_collision_soft_mode() -> None:
    with CoordStore(":memory:") as store:
        store.claim_ownership(resource_type="branch", resource_id="feat/x", agent_id="a1")
        soft = store.claim_ownership(
            resource_type="branch",
            resource_id="feat/x",
            agent_id="a2",
            raise_on_collision=False,
        )
        assert soft.inserted is False
        assert soft.collision is True
        assert soft.claim.agent_id == "a1"
        assert len(store.list_collisions()) == 1


def test_release_and_reclaim_by_other_agent() -> None:
    with CoordStore(":memory:") as store:
        store.claim_ownership(resource_type="issue", resource_id="3", agent_id="agent-a")
        assert store.release_ownership(
            resource_type="issue", resource_id="3", agent_id="agent-a"
        )
        second = store.claim_ownership(
            resource_type="issue", resource_id="3", agent_id="agent-b"
        )
        assert second.inserted is True
        assert second.claim.agent_id == "agent-b"


def test_send_log_idempotency_key() -> None:
    with CoordStore(":memory:") as store:
        id1, inserted1 = store.log_send(
            agent_id="agent-a",
            channel="github_issue_comment",
            target="issue/3",
            summary="progress note",
            idempotency_key="comment-3-progress-1",
        )
        id2, inserted2 = store.log_send(
            agent_id="agent-a",
            channel="github_issue_comment",
            target="issue/3",
            summary="progress note retry",
            idempotency_key="comment-3-progress-1",
        )
        assert inserted1 is True
        assert inserted2 is False
        assert id1 == id2
        sends = store.list_sends(agent_id="agent-a")
        assert len(sends) == 1
