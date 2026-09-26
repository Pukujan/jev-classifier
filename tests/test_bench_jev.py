"""Offline tests for the synthetic-plumbing JEV bench harness (#57).

No network, no live model: the stub mode and the scoring math are the unit
under test. The live path is exercised once on the owner's MacBook Pro host
(evidence posted on #57), never in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "bench_jev.py"
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bench_jev  # noqa: E402


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


class TestFixturesLoad:
    def test_all_fixture_samples_load_with_hashes(self):
        rows = bench_jev.load_fixtures()
        assert len(rows) == 17, "fixture files changed shape — bench expectations"
        assert {r["task"] for r in rows} == {"claim_type", "contradiction"}
        for r in rows:
            assert r["gold"] in r["options"], "gold label must be in option set"
            assert len(r["fixture_sha256_16"]) == 16
            assert r["text"].strip()

    def test_options_are_subsets_of_criteria_vocab(self):
        rows = bench_jev.load_fixtures()
        for r in rows:
            assert set(r["options"]) <= set(bench_jev.CRITERIA), r["options"]


class TestScoringMath:
    def test_exact_match_and_macro_f1(self):
        results = [
            {"task": "t", "gold": "a", "pred": "a"},
            {"task": "t", "gold": "a", "pred": "b"},
            {"task": "t", "gold": "b", "pred": "b"},
            {"task": "t", "gold": "b", "pred": "b"},
        ]
        out = bench_jev.score(results)["t"]
        assert out["samples"] == 4 and out["valid"] == 4
        assert out["correct"] == 3
        assert out["synthetic_plumbing_accuracy"] == 0.75
        # macro-F1: a: tp1 fp0 fn1 -> p=1.0 r=0.5 f1=2/3; b: tp2 fp1 fn0 ->
        # p=2/3 r=1.0 f1=4/5; mean(2/3, 4/5) = 0.7333
        assert abs(out["macro_f1_synthetic_only"] - 0.7333) < 0.0001

    def test_invalids_excluded_from_numerators(self):
        results = [
            {"task": "t", "gold": "a", "pred": "a"},
            {"task": "t", "gold": "a", "pred": "unknown", "invalid": True},
        ]
        out = bench_jev.score(results)["t"]
        assert out["valid"] == 1 and out["invalid_or_out_of_set"] == 1
        assert out["synthetic_plumbing_accuracy"] == 1.0, (
            "an invalid answer must never count as correct"
        )

    def test_all_invalid_gives_none_accuracy(self):
        results = [{"task": "t", "gold": "a", "pred": None, "invalid": True}]
        out = bench_jev.score(results)["t"]
        assert out["synthetic_plumbing_accuracy"] is None


class TestStubMode:
    def test_stub_is_deterministic(self, tmp_path):
        r1 = run_cli("--stub", "--report", str(tmp_path / "a.json"))
        r2 = run_cli("--stub", "--report", str(tmp_path / "b.json"))
        assert r1.returncode == 0 and r2.returncode == 0
        assert r1.stdout == r2.stdout, "stub bench must be byte-reproducible"
        assert json.loads((tmp_path / "a.json").read_text())["mode"] == "stub"

    def test_stdout_is_machine_readable_and_disclaims(self):
        r = run_cli("--stub")
        assert r.returncode == 0
        payload = json.loads(r.stdout)
        assert payload["bench"] == "jev_synthetic_plumbing_v1"
        assert payload["samples"] == 17
        # the number must never be quotable as #21 fidelity (arbiter rule)
        assert "NOT #21 claim-level fidelity" in r.stderr
        assert "Do not quote as research quality." in r.stderr

    def test_report_has_host_and_per_sample_rows(self, tmp_path):
        rep = tmp_path / "r.json"
        run_cli("--stub", "--report", str(rep))
        d = json.loads(rep.read_text())
        for key in ("platform", "python", "utc", "machine"):
            assert key in d["host"], key
        assert len(d["per_sample"]) == 17
        assert all({"sample_id", "task", "gold", "pred", "valid"}
                   <= set(row) for row in d["per_sample"])
    def test_live_mode_without_key_refuses_closed(self, tmp_path, monkeypatch, capsys):
        """CLI-level fail-closed: live mode with no key anywhere must print
        config_error and exit 2 — never emit fabricated answers.

        REPO_ROOT is patched to an empty dir so bench's .env loader finds no
        key; the env var is stripped; DecisionsClient then raises and main()
        maps it to exit 2. Fixture constants still load (absolute paths), so
        the failure is provably the missing credential, not missing data.
        """
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setattr(bench_jev, "REPO_ROOT", tmp_path)
        rc = bench_jev.main([])
        err = capsys.readouterr().err
        assert rc == 2
        assert "config_error" in err
