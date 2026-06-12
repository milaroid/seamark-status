#!/usr/bin/env bash
# m-statusline setup engine, invoked by the /m-statusline:setup plugin command.
#
# Copies the statusline.py sitting next to this script to
# ~/.claude/m-statusline.py and wires the statusLine block into
# ~/.claude/settings.json (backing the file up to settings.json.bak first).
# Re-running is safe; it just refreshes both.
set -euo pipefail

DEST="$HOME/.claude/m-statusline.py"
SETTINGS="$HOME/.claude/settings.json"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/statusline.py"

command -v python3 >/dev/null 2>&1 || { echo "error: python3 is required" >&2; exit 1; }
[ -f "$SRC" ] || { echo "error: statusline.py not found next to install.sh ($SRC)" >&2; exit 1; }

mkdir -p "$HOME/.claude"
cp "$SRC" "$DEST"

python3 - "$SETTINGS" <<'PY'
import json, os, shutil, sys

settings_path = sys.argv[1]
cfg = {}
if os.path.exists(settings_path):
    shutil.copy2(settings_path, settings_path + ".bak")
    with open(settings_path) as fh:
        cfg = json.load(fh)

cfg["statusLine"] = {
    "type": "command",
    "command": "python3 ~/.claude/m-statusline.py",
    "refreshInterval": 10,
}

with open(settings_path, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")

print("statusLine wired in " + settings_path
      + (" (previous settings backed up to settings.json.bak)"
         if os.path.exists(settings_path + ".bak") else ""))
PY

echo "installed: $DEST"
echo "restart Claude Code (or start a new session) and the duck starts running 🦆"
