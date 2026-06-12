---
description: Show the big burn duck with current rate-limit pace
disable-model-invocation: false
---

Show the user the big burn duck.

Steps:

1. Run exactly this command (the script is installed by /m-statusline:setup):

   ```sh
   python3 ~/.claude/m-statusline.py --status
   ```

2. The output is colored half-block pixel art plus two rate-limit bars.
   Present it to the user verbatim; do not summarize, reformat, or strip it.

3. If it prints "no cached statusline data yet", tell the user the statusline
   has to render at least once first (it caches its data on every refresh).

4. If the script file is missing, tell the user to run /m-statusline:setup.
