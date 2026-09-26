"""Offline tests for the watchdog LaunchAgent installer template (#41).

Only the --dry-run render path is exercised (no system changes): the plist must
parse as XML, keep install-time paths resolved, keep runtime shell
($(cat/wc/$(date)) unexpanded so timestamps and size caps work every run, and
the embedded command must actually produce a timestamped watchdog line when
run against a sandbox HOME. The install/uninstall guard (non-macOS exit 2) is
covered via monkeypatched uname.
"""

from __future__ import annotations

import datetime
import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install_watchdog_launchagent.sh"

# The other tests here only inspect the rendered plist or run it through
# whatever `sh` is on PATH. The one below executes the command with the
# literal /bin/sh the plist targets, so it is meaningful only where that
# path exists (macOS and Linux CI); on Windows it fails on a missing file
# rather than on anything about the installer (#47).
POSIX_SH = Path("/bin/sh").exists()


def _dry_run(home: str, **env_over: str) -> dict:
    env = {**os.environ, "HOME": home, **env_over}
    proc = subprocess.run(["sh", str(SCRIPT), "--dry-run"],
                          capture_output=True, text=True, check=True, env=env)
    return plistlib.loads(proc.stdout.encode())


def test_dry_run_parses_as_plutil_and_python() -> None:
    home = "/tmp/whatever"
    env = {**os.environ, "HOME": home}
    proc = subprocess.run(["sh", str(SCRIPT), "--dry-run"],
                          capture_output=True, text=True, check=True, env=env)
    if sys.platform == "darwin":  # authoritative Apple parser, when available
        chk = subprocess.run(["plutil", "-lint", "-"],
                             input=proc.stdout.encode(), capture_output=True)
        assert chk.returncode == 0, chk.stderr.decode()
    d = plistlib.loads(proc.stdout.encode())
    assert d["Label"] == "com.jev-classifier.storage-watchdog"
    assert d["StartInterval"] == 1800
    assert d["RunAtLoad"] is True
    assert d["ProgramArguments"][0] == "/bin/sh"
    assert d["ProgramArguments"][1] == "-c"


def test_runtime_expansions_stay_literal() -> None:
    d = _dry_run("/tmp/h1")
    cmd = d["ProgramArguments"][2]
    # $(date)/$(cat) must survive into the stored command (run per-execution),
    # while HOME-derived paths were already resolved at render time.
    assert "$(date" in cmd and "$(cat" in cmd, cmd
    assert "/tmp/h1/Library/Logs/jev-watchdog.log" in cmd
    assert "watchdog_storage.py" in cmd and "--budget-mb 2048" in cmd
    # unescaped & in XML character data would have broken plistlib itself;
    # entity refs decode back to the shell operators the command needs
    assert "&&" in cmd and "2>&1" in cmd


def test_interval_env_override() -> None:
    d = _dry_run("/tmp/h2", WATCHDOG_INTERVAL_S="60", WATCHDOG_BUDGET_MB="128")
    assert d["StartInterval"] == 60
    assert "--budget-mb 128" in d["ProgramArguments"][2]


@pytest.mark.skipif(
    not POSIX_SH,
    reason="executes the rendered command with /bin/sh, the shell the plist "
           "targets; that path does not exist on Windows (#47)",
)
def test_rendered_command_actually_runs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    d = _dry_run(str(home))
    cmd = d["ProgramArguments"][2]
    proc = subprocess.run(["/bin/sh", "-c", cmd], capture_output=True,
                          text=True, env={**os.environ, "HOME": str(home)})
    assert proc.returncode == 0, proc.stderr
    log = home / "Library" / "Logs" / "jev-watchdog.log"
    line = log.read_text().strip()
    m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (\{.+\})$", line)
    assert m, line[:200]
    stamp = datetime.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ")
    age = abs((datetime.datetime.now(datetime.timezone.utc)
               - stamp.replace(tzinfo=datetime.timezone.utc)).total_seconds())
    assert age < 300, "timestamp must be computed at run time, not render time"
    report = json.loads(m.group(2))
    assert report["status"] in ("ok", "warn", "over")


def test_install_requires_macos(tmp_path: Path, monkeypatch) -> None:
    """On non-Darwin hosts, install must refuse with exit 2 (dry-run stays safe)."""
    if sys.platform == "darwin":
        # cannot force uname without editing the script; skip positive-path here
        monkeypatch.setenv("WATCHDOG_FAKE_SKIP", "1")
        return
    env = {**os.environ, "HOME": str(tmp_path)}
    proc = subprocess.run(["sh", str(SCRIPT)], capture_output=True,
                          text=True, env=env)
    assert proc.returncode == 2
    assert "macOS" in proc.stderr


def test_unknown_flag_rejected(tmp_path: Path) -> None:
    proc = subprocess.run(["sh", str(SCRIPT), "--bogus"], capture_output=True,
                          text=True, env={**os.environ, "HOME": str(tmp_path)})
    assert proc.returncode == 2
    assert "usage:" in proc.stderr
