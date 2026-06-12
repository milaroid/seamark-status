# m-statusline

A three-line [Claude Code](https://claude.com/claude-code) statusline that shows the
active model, your git branch, your `/m` pipeline stage, and **pace-aware** usage
bars that project where your 5-hour and weekly limits will land at reset — then
forecasts when you'll hit the limit at the current rate. An innocent-looking 60%
that is on track to blow past 100% reads red *now* instead of at reset time.

Single file. Python standard library only. No dependencies.

```
Opus 4.8  ·  ⎇ main ●3 ↑1  ·  m implement ◉◉◐○○ 2/5
CTX ███░░░░░ 41%  ·  5H ██░░░░░░ 23%→41% ·2h13m  ·  WK ████░░░░ 76%→104% ·1d20h
→ WK cap ~6h  ·  ›››toasty
```

(In the terminal each segment is colored by load; the block above is the
plain-text shape.)

## What each segment means

**Line 1: identity**

| Segment | Meaning |
|---|---|
| `Opus 4.8` | Active model display name. |
| `⎇ main ●3 ↑1` | Git branch, with `●` uncommitted count, `↑` commits ahead, `↓` behind. Shows the worktree name (`⌂name`) inside a worktree, a short SHA when detached, and nothing outside a repo. |
| `m implement ◉◉◐○○ 2/5` | Current `/m:develop` phase and progress across the pipeline. `◉` done · `◐` current · `○` pending. Hidden when you are not inside an active `/m:develop` run. |

**Line 2: metrics**

| Segment | Meaning |
|---|---|
| `CTX ███░░░░░ 41%` | Context window used. |
| `5H … 23%→41%` | 5-hour rate limit: used now → **projected** at window end. |
| `WK … 76%→104%` | 7-day rate limit: used now → projected at window end. |
| `·1d20h` | Time until that window resets. |

**Line 3: forecast**

| Segment | Meaning |
|---|---|
| `→ WK cap ~6h` | Forecast verdict. When a window is projected to blow its limit, this is the window and the time until you hit 100% at the current rate. Otherwise `clear`/`tight` with the soonest reset. |
| `›››toasty` | A pace tag: a tier-colored speed streak (one chevron strolling, two sprinting, three on fire) and a one-word mood that rotates every two minutes. |

The branch is read by running `git` in your working directory (the statusLine
JSON carries no current-branch field) and is cached for a few seconds so the
once-per-second refresh never spawns a subprocess storm.

### Colors

Each bar and percentage is colored by load. The rate-limit bars follow the
**projection**, not the raw used value:

| Color | Threshold |
|---|---|
| green | under 50% |
| yellow | 50–80% |
| red | 80%+ |

The projection is suppressed for the first 2% of a window, where it is just noise.

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
- `color_for()`: the bars' green / yellow / red thresholds.
- `TAGS`: the one-word pace tags per tier.
- `pace_tier()`: the strolling / sprinting / on-fire cutoffs.
- `ROTATE_SECONDS`: how often the tag rotates (default 120).
- `GIT_TTL`: how long git state is cached, in seconds (default 5).
- `PIPELINE`: the list of `/m` phases to track.

## Requirements

- Python 3 (standard library only).
- Claude Code with statusLine support.

## License

MIT, see [LICENSE](LICENSE).
