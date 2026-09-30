# m-statusline

The cockpit for the [`/seamark` pipeline](https://github.com/milorad-teodorovic/m-pipeline):
a [Claude Code](https://claude.com/claude-code) statusline that shows your git
branch and ticket, **pace-aware** usage bars that project where your 5-hour and
weekly limits will land at reset, and — when the pipeline drives Codex or Kimi
as a second engine — a parallel second-engine usage row plus a live per-run
token-burn gauge. While `/seamark:develop` runs, a cockpit line tracks the phase, its runtime, the
task flow, and open blockers — live, from the `.seamark/` state the pipeline writes.
Without Seamark it degrades to a clean git + usage statusline, but the cockpit
is the point.

Single file. Python standard library only. No dependencies.

```
┃●┃ Seamark │ api │ ⎇ feat/ENG-142 ●3 ↑1 │ ENG-142
s implement ◉◉◐○○ 2/5 ·12m │ tasks 4/6
Opus 5.5 high     CTX ███▎░░░░ 41% │ 5H █▊▒▒░░░░ 23%→41% │ WK ██████▏▒ 76%→104% ↻1d20h
gpt-6-astra high  · idle
```

Each usage row is prefixed with its model name and reasoning effort as one unit
in a single colour (Claude row in Claude orange, second-engine row in grey). The
second-engine row is present throughout a `/seamark:develop` run when an engine is
configured — `· idle` between passes, a live `burn` gauge during plan and
review — and hidden when the provider is `none`.

(In the terminal each segment is colored by load; the block above is the
plain-text shape.)

## What each segment means

**Line 1: identity**

| Segment | Meaning |
|---|---|
| `┃●┃ Seamark` | The Seamark mark (two teal posts around a blue dot) and the name. On a narrow terminal, only the mark shows. |
| `m-pipeline` | Name of the current folder, in bold. |
| `⎇ main ●3 ↑1` | Git branch, with `●` uncommitted count, `↑` commits ahead, `↓` behind. Shows the worktree name (`⌂name`) inside a worktree, a short SHA when detached, and nothing outside a repo. Links to the branch on the origin host. |
| `ENG-142` | Jira ticket captured from the branch via `.seamark/jira.yml` `branchPattern`. Links to `https://<site>/browse/ENG-142` when `.seamark/jira.yml` sets `site`. |
| `PR #6 draft` | The open PR (or GitLab MR) for this branch, from Claude Code's `pr` fields, linked to the PR page. The state reads `draft` (dim), `review` (amber), `changes` (red), or `approved` (green). |
| `s ✗ last run BLOCKED` / `s idx stale 42d` | Idle pipeline alerts: shown only when the last run blocked or the index is stale. Silent otherwise. |

Links use OSC 8 escape codes: Cmd+click (macOS) or Ctrl+click opens them in
terminals that support hyperlinks, such as iTerm2, Kitty, and WezTerm. Other
terminals show plain text.

The active model is no longer on the identity line — it labels its own usage row instead (see Line 2/3 below).

**Pipeline cockpit (appears while `/seamark:develop` runs)**

| Segment | Meaning |
|---|---|
| `s implement ◉◉◐○○ 2/5 ·12m` | Phase dots (`◉` done · `◐` current · `○` pending), the running phase, and how long it has been running (mtime of the phase marker). A sixth dot appears when the readiness gate starts. |
| `loop 2/3 ·4 left` | The `/seamark:verify` loop counter and remaining issues, parsed from `.seamark/PROGRESS.md`. Iterate phase only. |
| `tasks 4/6` | Task progress (completed/total) from `.seamark/TASKS.md`. |

**Line 2: Claude metrics** — prefixed with the active model name (in Claude orange)

| Segment | Meaning |
|---|---|
| `Opus 5.5 high` | Active model display name plus the live reasoning effort (`effort.level` from Claude Code; falls back to `~/.claude/settings.json` `effortLevel`), labeling this row. A `⚡` follows when fast mode is on. |
| `CTX ███▎░░░░ 41%` | Context window used. Bars fill in eighth-cell steps. |
| `5H █▊▒▒░░░░ 23%→41%` | 5-hour rate limit: used now → **projected** at window end. The bright fill is the used value; a dimmer shade of the same color extends to the projection. |
| `WK … 76%→104%` | 7-day rate limit: used now → projected at window end. |
| `↻1d20h` | Time until that window resets. Shown only when the window load is 50% or more. |
| `cache 92%` | Prompt cache hit ratio for the session (`prompt_cache.hit_ratio`). Dim while the cache is warm, amber once it has gone cold. Absent until caching is observed. |

**Narrow terminals.** The statusline reads `COLUMNS` and drops detail until the
widest usage row fits: first the reset countdowns, then the projection arrows,
then it shortens the bars from 8 to 5 cells, then it drops the cache segment. The
To Himself line is hidden when it does not fit.

**Line 3: second-engine metrics** — prefixed with the engine model name (in grey). Present throughout a `/seamark:develop` run whenever `.seamark/pipeline.yml` selects `second_engine.provider: codex` or `kimi`: a dim `· idle` between passes, the live `burn` gauge while the engine drives **plan** and **review**. Hidden when the provider is `none`.

| Segment | Meaning |
|---|---|
| `gpt-6-astra high` | Codex model + reasoning effort: the last run's snapshot, else `second_engine.model` / `reasoning_effort`, else `~/.codex/config.toml`. |
| `kimi-k3 high` | Kimi model alias (`kimi-code/` shortened to `kimi-`) + effort, from `second_engine.model` / `reasoning_effort` (default `kimi-code/k3`, `high`). |
| `· idle` | The engine is configured for this `/seamark:develop` run but no pass is currently burning tokens (refine / implement / verify phases). |
| `burn ███▋░░░░ 92k/200k` | Live per-pass engine token spend vs `second_engine.token_budget` (default 200k), while a `plan` or `review` pass runs. |

The `burn` gauge reads `.seamark/handoff/<provider>-meter.txt` (`codex-meter.txt` or `kimi-meter.txt`: the live per-pass token total, created during a pass and removed when it ends). The row's presence is gated on `.seamark/DEVELOP_ACTIVE` plus the `second_engine:` block in `.seamark/pipeline.yml`. A legacy `codex:` block with `enabled: true` still selects Codex when no `second_engine:` block exists.

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
(`#E67D22`) for the Claude row, grey (`#AAAAAA`) for the Codex row. The grey
stays readable on light and dark themes.

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

## `/seamark` pipeline integration

The `s <phase> ◉◉◐○○` segment reads a `.seamark/DEVELOP_ACTIVE` marker (with a
`current_phase:` line) and per-phase `phase-<name>-done` files, walking up from the
current directory to find them. The pipeline tracked is:

```
refine → plan → implement → review → verify → readiness (when started)
```

This is the convention used by the
[`/seamark` pipeline](https://github.com/milorad-teodorovic/m-pipeline). If you do not use
it, the segment simply never appears and the rest of the statusline works unchanged.
The dependency is one-way and optional.

## Customizing

Everything tweakable lives near the top of `statusline.py`:

- `BAR_WIDTH`: width of the usage bars in cells.
- `FITS`: the narrow-terminal steps, from full to most compact.
- `WIDTH_MARGIN`: cells kept free at the right edge (default 4).
- `PR_STATES`: the word and color for each PR review state.
- `color_for()`: the load-ladder thresholds (blue / green / amber / red).
- `CLAUDE_ORANGE` / `CODEX_GREY`: the per-row model-label colors.
- `COUNTDOWN_MIN_LOAD`: the window load (percent) at which the reset countdown appears (default 50).
- `CODEX_FRESH_TTL`: how long (seconds) since the last Codex run the Codex row stays visible (default 6h).
- `GIT_TTL`: how long git state is cached, in seconds (default 5).
- `PIPELINE`: the list of `/seamark` phases to track. Readiness is added when its phase starts.

## Requirements

- Python 3 (standard library only).
- Claude Code with statusLine support.

## License

MIT, see [LICENSE](LICENSE).
