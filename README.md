# m-statusline

The cockpit for the [`/m` pipeline](https://github.com/milorad-teodorovic/m-pipeline):
a [Claude Code](https://claude.com/claude-code) statusline that shows your git
branch and ticket, **pace-aware** usage bars that project where your 5-hour and
weekly limits will land at reset, and — when the pipeline drives Codex as a
second engine — a parallel **Codex** usage row plus a live per-run token-burn
gauge. While `/m:develop` runs, a cockpit line tracks the phase, its runtime, the
task flow, and open blockers — live, from the `.m/` state the pipeline writes.
Without m-pipeline it degrades to a clean git + usage statusline, but the cockpit
is the point.

Single file. Python standard library only. No dependencies.

```
⎇ feat/ENG-142 ●3 ↑1  ·  ENG-142
m implement ◉◉◐○○ 2/5 ·12m  ·  tasks 4/6
Opus 4.8 · xhigh  CTX ███░░░░░ 41%  ·  5H ██░░░░░░ 23%→41% ·2h13m  ·  WK ████░░░░ 76%→104% ·1d20h
gpt-5.5 · xhigh   · idle
```

Each usage row is prefixed with its model name and reasoning effort as one unit
in a single colour (Claude row in Claude orange, Codex row in white). The Codex
row is present throughout a `/m:develop` run when Codex is enabled — `· idle`
between passes, a live `burn` gauge during plan and review — and hidden when
Codex is disabled.

(In the terminal each segment is colored by load; the block above is the
plain-text shape.)

## What each segment means

**Line 1: identity**

| Segment | Meaning |
|---|---|
| `⎇ main ●3 ↑1` | Git branch, with `●` uncommitted count, `↑` commits ahead, `↓` behind. Shows the worktree name (`⌂name`) inside a worktree, a short SHA when detached, and nothing outside a repo. |
| `ENG-142` | Jira ticket captured from the branch via `.m/jira.yml` `branchPattern`. |
| `m ✗ last run BLOCKED` / `m idx stale 42d` | Idle pipeline alerts: shown only when the last run blocked or the index is stale. Silent otherwise. |

The active model is no longer on the identity line — it labels its own usage row instead (see Line 2/3 below).

**Pipeline cockpit (appears while `/m:develop` runs)**

| Segment | Meaning |
|---|---|
| `m implement ◉◉◐○○ 2/5 ·12m` | Phase dots (`◉` done · `◐` current · `○` pending), the running phase, and how long it has been running (mtime of the phase marker). |
| `loop 2/3 ·4 left` | The `/m:iterate` loop counter and remaining issues, parsed from `.m/PROGRESS.md`. Iterate phase only. |
| `tasks 4/6` | Task progress (completed/total) from `.m/TASKS.md`. |

**Line 2: Claude metrics** — prefixed with the active model name (in Claude orange)

| Segment | Meaning |
|---|---|
| `Opus 4.8 · xhigh` | Active model display name plus reasoning effort (from `~/.claude/settings.json` `effortLevel`), labeling this row. |
| `CTX ███░░░░░ 41%` | Context window used. |
| `5H … 23%→41%` | 5-hour rate limit: used now → **projected** at window end. |
| `WK … 76%→104%` | 7-day rate limit: used now → projected at window end. |
| `·1d20h` | Time until that window resets. |

**Line 3: Codex metrics** — prefixed with the Codex model name (in white). Present throughout a `/m:develop` run whenever Codex is enabled: a dim `· idle` between passes, the live `burn` gauge while Codex drives **plan** and **review** as the second engine. Hidden when Codex is disabled.

| Segment | Meaning |
|---|---|
| `gpt-5.5 · xhigh` | Codex model + reasoning effort, from `~/.codex/config.toml` `model` / `model_reasoning_effort`. |
| `· idle` | Codex is enabled for this `/m:develop` run but no pass is currently burning tokens (refine / implement / iterate phases). |
| `burn █████░░░ 92k/200k` | Live per-pass Codex token spend vs the `token_budget` (default 200k), while a `plan` or `review` pass runs. |

The `burn` gauge reads `.m/handoff/codex-meter.txt` (the live per-pass token total, created during a Codex pass and removed when it ends); the row's presence is gated on `.m/DEVELOP_ACTIVE` plus `codex.enabled: true` in `.m/pipeline.yml`.

> Persistent 5-hour / weekly Codex usage bars (mirroring the Claude row) are not currently shown: `codex exec` emits `rate_limits: null`, so the account snapshot at `~/.claude/.codex-limits.json` is never written. They return if codex-cli exposes rate limits in exec mode ([openai/codex#14728](https://github.com/openai/codex/issues/14728)).

The branch is read by running `git` in your working directory (the statusLine
JSON carries no current-branch field) and is cached for a few seconds so the
once-per-second refresh never spawns a subprocess storm.

### Colors

Bar fills climb the same load ladder, driven by their own progress. The Claude
rate-limit bars feed it their **projection**, not the raw used value; CTX and the
Codex usage bars feed it the used value:

| Color | Load |
|---|---|
| blue | under 50% |
| green | 50–70% |
| amber | 70–90% |
| red | 90%+ |

The projection is suppressed for the first 2% of a window, where it is just noise.

Each usage row's **model-name label** is brand-colored instead: Claude orange
(`#E67D22`) for the Claude row, white (`#FFFFFF`) for the Codex row.

## Install

Inside Claude Code:

```
/plugin marketplace add milorad-teodorovic/m-statusline
/plugin install m-statusline@m-statusline
/m-statusline:setup
```

The setup command copies the bundled script to `~/.claude/m-statusline.py` and
wires the `statusLine` block into `~/.claude/settings.json` (existing settings
preserved, previous file backed up to `settings.json.bak`). Restart Claude Code
and the pace banner lights up. Re-running setup is safe; it just refreshes the
script and the settings block.

There are no packages. The script reads the
[statusLine stdin JSON](https://platform.claude.com/docs/en/statusline) Claude Code
feeds it and writes the two lines back.

### Uninstall

Delete the `statusLine` block from `~/.claude/settings.json` and remove
`~/.claude/m-statusline.py`.

## `/m` pipeline integration

The `m <phase> ◉◉◐○○` segment reads a `.m/DEVELOP_ACTIVE` marker (with a
`current_phase:` line) and per-phase `phase-<name>-done` files, walking up from the
current directory to find them. The pipeline tracked is:

```
refine → plan → implement → review → iterate
```

This is the convention used by the
[`/m` pipeline](https://github.com/milorad-teodorovic/m-pipeline). If you do not use
it, the segment simply never appears and the rest of the statusline works unchanged.
The dependency is one-way and optional.

## Customizing

Everything tweakable lives near the top of `statusline.py`:

- `BAR_WIDTH`: width of the usage bars in cells.
- `color_for()`: the load-ladder thresholds (blue / green / amber / red).
- `CLAUDE_ORANGE` / `CODEX_WHITE`: the per-row model-label colors.
- `CODEX_FRESH_TTL`: how long (seconds) since the last Codex run the Codex row stays visible (default 6h).
- `GIT_TTL`: how long git state is cached, in seconds (default 5).
- `PIPELINE`: the list of `/m` phases to track.

## Requirements

- Python 3 (standard library only).
- Claude Code with statusLine support.

## License

MIT, see [LICENSE](LICENSE).
