"""System spec drift tests (Issue #30, parent #21 child leaf 1).

The prose spec (docs/SYSTEM_SPEC.md) and the machine-readable contract index
(docs/spec/modules.json) must agree. These tests fail when either drifts from
the other or from the code, so the spec cannot rot silently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC_MD = ROOT / "docs" / "SYSTEM_SPEC.md"
SPEC_JSON = ROOT / "docs" / "spec" / "modules.json"

# Module ids the spec must cover, per docs/SYSTEM_SPEC.md section 2.
EXPECTED_MODULES = {"M1", "M2", "M3", "M4", "M5", "M6", "M7", "C", "O", "B"}

# Only JEV may produce deterministic classifier output (AGENTS.md hard rule).
JEV_ROLES = {"jev", "jev_plus_deterministic"}


@pytest.fixture(scope="module")
def index() -> dict:
    return json.loads(SPEC_JSON.read_text(encoding="utf-8"))


def test_spec_files_exist() -> None:
    assert SPEC_MD.is_file(), "docs/SYSTEM_SPEC.md missing"
    assert SPEC_JSON.is_file(), "docs/spec/modules.json missing"


def test_index_has_spec_version_and_matches_prose(index: dict) -> None:
    version = index["spec_version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"bad spec_version {version!r}"
    text = SPEC_MD.read_text(encoding="utf-8")
    assert f"spec_version: {version}" in text, "prose spec_version != index spec_version"


def test_index_covers_every_documented_module(index: dict) -> None:
    ids = {m["id"] for m in index["modules"]}
    assert ids == EXPECTED_MODULES, f"module ids drift: {ids ^ EXPECTED_MODULES}"


def test_prose_documents_every_indexed_module(index: dict) -> None:
    text = SPEC_MD.read_text(encoding="utf-8")
    for module in index["modules"]:
        # Each module appears as a "### <id> —" heading in section 2.
        assert re.search(rf"^### {re.escape(module['id'])} ", text, re.M), (
            f"module {module['id']} indexed but not documented in prose"
        )


def test_every_module_names_its_role_and_at_most_one_is_jev_decisions(index: dict) -> None:
    roles = {m["id"]: m["role"] for m in index["modules"]}
    for mid, role in roles.items():
        assert role, f"module {mid} has empty role"
    # M3 is the sole semantic judge; B uses JEV only for closed questions.
    jev_modules = {mid for mid, role in roles.items() if role in JEV_ROLES}
    assert jev_modules == {"M3", "B"}, f"unexpected JEV-role modules: {jev_modules}"
    assert roles["M3"] == "jev", "M3 must be JEV-only"


def test_no_non_jev_module_claims_a_deterministic_output_role(index: dict) -> None:
    """The role table forbids any non-JEV model producing classifier output."""
    for module in index["modules"]:
        if module["role"] in JEV_ROLES:
            continue
        blob = json.dumps(module).lower()
        assert "non-jev model produces labels" not in blob
        # M1 is the only untrusted-input producer and must be flagged non-jev.
        if module["id"] == "M1":
            assert module["role"] == "non-jev"


def test_all_modules_fail_closed(index: dict) -> None:
    for module in index["modules"]:
        assert module["fail_closed"] is True, f"{module['id']} must fail closed"


def test_required_claim_keys_match_code(index: dict) -> None:
    from jev_classifier.classify import REQUIRED_CLAIM_KEYS

    m4 = next(m for m in index["modules"] if m["id"] == "M4")
    assert set(m4["contract"]["required_keys"]) == set(REQUIRED_CLAIM_KEYS), (
        "index M4 required_keys != classify.REQUIRED_CLAIM_KEYS"
    )


def test_required_paper_sections_match_code(index: dict) -> None:
    from jev_classifier.paper.assemble import REQUIRED_SECTIONS

    m7 = next(m for m in index["modules"] if m["id"] == "M7")
    assert m7["contract"]["required_sections"] == list(REQUIRED_SECTIONS), (
        "index M7 required_sections != assemble.REQUIRED_SECTIONS"
    )


def test_jev_endpoint_and_pin_match_code(index: dict) -> None:
    from jev_classifier.decisions import DEFAULT_MODEL, DEFAULT_URL

    rule = index["jev_only_rule"]
    assert rule["endpoint"] == DEFAULT_URL
    assert rule["pinned_model"] == DEFAULT_MODEL


def test_declared_vs_implemented_primitives_record_the_score_gap(index: dict) -> None:
    """score is declared but unimplemented; the index must say so, not hide it."""
    rule = index["jev_only_rule"]
    assert "score" in rule["primitives_declared"]
    assert "score" not in rule["primitives_implemented"]
    assert rule["primitives_implemented"] == ["choice", "noul"]
    assert "32" in str(rule["note"]) or "#32" in rule["note"]


def test_score_primitive_still_absent_from_code(index: dict) -> None:
    """Guard: if score lands, this test fails so the index gets updated too."""
    import jev_classifier.normalize as norm

    has_score = hasattr(norm, "normalize_score_answer")
    implemented = "score" in index["jev_only_rule"]["primitives_implemented"]
    assert has_score == implemented, (
        "normalize_score_answer presence disagrees with primitives_implemented; "
        "update docs/spec/modules.json (see issue #32)"
    )


def test_ops_schema_version_matches_code(index: dict) -> None:
    from jev_classifier.ops.store import SCHEMA_VERSION

    ops = next(m for m in index["modules"] if m["id"] == "O")
    assert ops["contract"]["schema_version"] == SCHEMA_VERSION


def test_coordination_and_ops_are_not_authority(index: dict) -> None:
    for mid in ("C", "O"):
        module = next(m for m in index["modules"] if m["id"] == mid)
        assert module["authority"] is False, f"{mid} must never be authority"


def test_prose_records_the_flat_validity_ruling() -> None:
    """The no-reasoner ruling must stay documented so it is not relitigated."""
    text = SPEC_MD.read_text(encoding="utf-8")
    assert "flat" in text.lower()
    assert "valid time" in text.lower()
    assert "PROV-O" in text


def test_ci_contexts_match_workflow(index: dict) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for context in index["ci"]["required_contexts"]:
        # Each required context name must appear in the workflow file.
        stem = context.split(" (")[0]
        assert stem in workflow, f"required context {context!r} not in ci.yml"


def test_branch_protection_strict_recorded(index: dict) -> None:
    assert index["ci"]["branch_protection"] == "strict"
    assert index["ci"]["force_push_blocked"] is True
    assert index["ci"]["deletion_blocked"] is True


def test_cross_cutting_invariants_present(index: dict) -> None:
    expected = {
        "fail_closed_everywhere",
        "confidence_is_not_correctness",
        "github_is_authority",
        "secrets_never_persist",
        "storage_stays_lean",
        "project_does_not_stop",
    }
    assert set(index["cross_cutting_invariants"]) == expected


def test_module_status_is_a_known_value(index: dict) -> None:
    known = {"merged", "in_flight", "partial"}
    for module in index["modules"]:
        assert module["status"] in known, f"{module['id']} bad status {module['status']!r}"


def test_every_module_has_at_least_one_test_path(index: dict) -> None:
    for module in index["modules"]:
        tests = module["tests"]
        assert tests, f"{module['id']} names no test"


def test_landed_module_paths_exist(index: dict) -> None:
    """Modules already on main must point at real files.

    An in_flight module legitimately lives on an unmerged branch (M1's grok
    capture is on feat/grok-source-bot), so it is exempt — but every merged or
    partial module is checked strictly, which is what caught the drift this
    test exists for.
    """
    checked = 0
    for module in index["modules"]:
        if module["status"] == "in_flight":
            continue
        for path in module["code"] + module["tests"]:
            if path.startswith("scripts/"):
                # Entrypoints, not pytest files; still must exist if listed.
                pass
            assert (ROOT / path).is_file(), f"{module['id']} path missing on main: {path}"
            checked += 1
    assert checked > 20, f"too few paths verified ({checked}); index looks hollow"


def test_in_flight_modules_are_tracked_by_an_issue(index: dict) -> None:
    """An in-flight module must name the issue that owns it, or it is unclaimed."""
    for module in index["modules"]:
        if module["status"] == "in_flight":
            assert module["issue"], f"{module['id']} in flight but names no issue"

