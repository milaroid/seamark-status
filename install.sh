#!/usr/bin/env bash
# m-statusline installer.
#
# Downloads statusline.py to ~/.claude/m-statusline.py and wires the
# statusLine block into ~/.claude/settings.json (backing the file up to
# settings.json.bak first). Re-running is safe; it just refreshes both.
#
#   curl -fsSL https://raw.githubusercontent.com/milorad-teodorovic/m-statusline/main/install.sh | bash
#
# Prefer to read before you run? Download it first:
#   curl -fsSL .../install.sh -o install.sh && less install.sh && bash install.sh
set -euo pipefail

RAW="${M_STATUSLINE_RAW:-https://raw.githubusercontent.com/milorad-teodorovic/m-statusline/main/statusline.py}"
DEST="$HOME/.claude/m-statusline.py"
SETTINGS="$HOME/.claude/settings.json"

command -v python3 >/dev/null 2>&1 || { echo "error: python3 is required" >&2; exit 1; }

mkdir -p "$HOME/.claude"

# When run from a checkout or a Claude Code plugin dir, statusline.py sits
# next to this script; use it directly. Piped through curl, fall back to RAW.
SRC_LOCAL="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)/statusline.py"
if [ -f "$SRC_LOCAL" ]; then
  cp "$SRC_LOCAL" "$DEST"
else
  curl -fsSL "$RAW" -o "$DEST"
fi

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
