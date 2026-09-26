#!/bin/sh
# Install the jev-classifier storage watchdog as a scheduled user LaunchAgent.
#
# Why: the owner's kickoff requires an AUTOMATED watchdog on the local
# machine (storage must not go haywire; GitHub is the canonical store).
# scripts/watchdog_storage.py is read-only and never deletes; this installer
# runs it on an interval and appends one JSON line per run to a self-capped
# log. The watchdog itself stays report-only.
#
# Usage:
#   scripts/install_watchdog_launchagent.sh              # install (macOS)
#   scripts/install_watchdog_launchagent.sh --dry-run    # print plist, no system change (any OS)
#   scripts/install_watchdog_launchagent.sh --uninstall  # bootout + remove plist (macOS)
#
# Tunables (env):
#   WATCHDOG_INTERVAL_S  seconds between runs (default 1800)
#   WATCHDOG_BUDGET_MB   working-tree budget before status=over (default 2048)
#   WATCHDOG_PYTHON      interpreter for watchdog_storage.py (default python3)
#
# Determinism: every path derives from $HOME and this script's own location,
# so the committed file contains no device-specific absolute paths (repo
# record policy). The generated plist (installed under ~/Library/LaunchAgents)
# embeds resolved paths and is NEVER committed.
set -eu

LABEL="com.jev-classifier.storage-watchdog"
SCRIPT_PATH=$(cd "$(dirname "$0")" && pwd -P)
REPO_ROOT=$(cd "$SCRIPT_PATH/.." && pwd -P)
INTERVAL=${WATCHDOG_INTERVAL_S:-1800}
BUDGET_MB=${WATCHDOG_BUDGET_MB:-2048}
PYTHON_BIN=${WATCHDOG_PYTHON:-$(command -v python3 || echo python3)}
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/jev-watchdog.log"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/$LABEL.plist"
MAX_LOG_BYTES=65536

render_plist() {
    # Unquoted heredoc: install-time values ($LOG_FILE, $REPO_ROOT, $INTERVAL,
    # ...) expand now; runtime shell work is escaped (\$f, \$(cat ...),
    # \$(date ...)) so the timestamp and log size are computed on EVERY run.
    # The embedded command must contain no literal '<' (invalid XML in a
    # plist character node) — size is checked via `cat | wc -c`, and '&' is
    # escaped as &amp;.
    cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/sh</string>
		<string>-c</string>
		<string>f='$LOG_FILE'; if [ -f "\$f" ] &amp;&amp; [ "\$(cat "\$f" | wc -c)" -gt $MAX_LOG_BYTES ]; then : > "\$f"; fi; mkdir -p '$LOG_DIR'; '$PYTHON_BIN' '$REPO_ROOT/scripts/watchdog_storage.py' --repo-root '$REPO_ROOT' --budget-mb $BUDGET_MB | sed "s|^|\$(date -u +%Y-%m-%dT%H:%M:%SZ) |" >> "\$f" 2>&amp;1</string>
	</array>
	<key>StartInterval</key>
	<integer>$INTERVAL</integer>
	<key>RunAtLoad</key>
	<true/>
	<key>Nice</key>
	<integer>10</integer>
	<key>StandardOutPath</key>
	<string>$LOG_FILE</string>
	<key>StandardErrorPath</key>
	<string>$LOG_FILE</string>
</dict>
</plist>
PLIST
}

need_macos() {
    if [ "$(uname -s)" != "Darwin" ]; then
        echo "install/uninstall require macOS (launchctl); use --dry-run here." >&2
        exit 2
    fi
}

case "${1:-}" in
    --dry-run)
        render_plist
        ;;
    --uninstall)
        need_macos
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        rm -f "$PLIST_FILE"
        echo "uninstalled $LABEL"
        ;;
    ""|--install)
        need_macos
        mkdir -p "$PLIST_DIR" "$LOG_DIR"
        render_plist > "$PLIST_FILE"
        # Idempotent reinstall: drop any previous instance first.
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"
        launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || true
        echo "installed $LABEL (every ${INTERVAL}s, budget ${BUDGET_MB}MB, log: $LOG_FILE)"
        ;;
    *)
        echo "usage: $0 [--dry-run|--uninstall]" >&2
        exit 2
        ;;
esac
