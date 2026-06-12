---
description: Install the m-statusline burn duck into ~/.claude/settings.json
disable-model-invocation: false
---

Wire the m-statusline statusline into the user's Claude Code settings.

Steps:

1. Run the bundled installer from the plugin directory:

   ```sh
   bash "$CLAUDE_PLUGIN_ROOT/install.sh"
   ```

   The installer copies the plugin's `statusline.py` to `~/.claude/m-statusline.py`
   and sets the `statusLine` block in `~/.claude/settings.json`. Existing settings
   are preserved; the previous file is backed up to `settings.json.bak`.

2. Quote the installer output to the user.

3. If the command fails, show the exact error and stop. Do not edit
   `~/.claude/settings.json` by hand and do not retry with elevated permissions.

4. On success, tell the user to restart Claude Code (or start a new session) to
   see the statusline, and that the duck speeds up as they burn through their
   rate limits: 🦆 strolling, 🦆💨 sprinting, 🦆🔥 on fire.
