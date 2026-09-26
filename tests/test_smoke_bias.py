"""Optional live bias-pack smoke (Issue #11).

Default offline suite never calls the live API.
- ``test_smoke_bias_skips_without_key`` always runs (subprocess, env cleared).
- ``test_smoke_bias_live`` is marked ``live`` and skips unless OPENROUTER_API_KEY
  is present in the parent environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke_bias.py"


def test_smoke_bias_script_exists() -> None:
    assert SCRIPT.is_file()
    text = SCRIPT.read_text(encoding="utf-8")
    assert "BIAS_PACK_V1" in text or "bias_pack_v1" in text
    assert "OPENROUTER_API_KEY" in text
    assert "typesafe/jev-1.13" in text


def test_smoke_bias_skips_without_key() -> None:
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    env.pop("OPENROUTER_API_KEY", None)
    # Ensure dotenv cannot re-inject from a local .env for this subprocess:
    # the script loads .env — so run with cwd but override key to empty after
    # is not enough. Force empty key in env so load_dotenv(override=False)
    # will not overwrite an explicit empty... actually load_dotenv override=False
    # only sets if key not in environ. So set empty string to block .env fill.
    env["OPENROUTER_API_KEY"] = ""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "SKIP" in proc.stdout
    # No secret leakage heuristics
    assert "sk-" not in proc.stdout.lower()
    assert "bearer" not in proc.stdout.lower()
    assert "authorization" not in proc.stdout.lower()


@pytest.mark.live
def test_smoke_bias_live() -> None:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        # Also try loading .env the same way the script does, without printing
        env_path = ROOT / ".env"
        if env_path.is_file():
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.partition("=")[2].strip().strip('"').strip("'")
                    break
    if not key:
        pytest.skip("OPENROUTER_API_KEY absent — live bias smoke skipped")

    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = key
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr!r} stdout={proc.stdout!r}"
    assert "SKIP" not in proc.stdout
    assert "pack_id" in proc.stdout
    assert "raised_flags" in proc.stdout
    assert "sk-" not in proc.stdout.lower()
    assert "bearer" not in proc.stdout.lower()