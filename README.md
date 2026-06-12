# m-statusline

A two-line [Claude Code](https://claude.com/claude-code) statusline that shows the
active model, your `/m` pipeline stage, and **pace-aware** usage bars that
project where your 5-hour and weekly limits will land at reset, so an innocent-looking
60% that is on track to blow past 100% reads red *now* instead of at reset time.

Single file. Python standard library only. No dependencies.

```
Opus 4.8  ·  m implement ◉◉◐○○ 2/5
CTX ███░░░░░ 41%  ·  5H 🦆 ██░░░░░░ 23%→41% ·2h13m  ·  WK 🦆🔥 ████░░░░ 55%→109% ·3d11h
```

(In the terminal each segment is colored green / yellow / red by load. The block
above is the plain-text shape.)

## What each segment means

**Line 1: identity**

| Segment | Meaning |
|---|---|
| `Opus 4.8` | Active model display name. |
| `m implement ◉◉◐○○ 2/5` | Current `/m:develop` phase and progress across the pipeline. `◉` done · `◐` current · `○` pending. Hidden entirely when you are not inside an active `/m:develop` run. |

**Line 2: metrics**

| Segment | Meaning |
|---|---|
| `CTX ███░░░░░ 41%` | Context window used. |
| `5H … 23%→41%` | 5-hour rate limit: used now → **projected** at window end. |
| `WK … 55%→109%` | 7-day rate limit: used now → projected at window end. |
| `·2h13m` | Time until that window resets. |

### The pace banner

The metrics line ends with a pace banner that reads the same projection as the
bars (`used% × window / elapsed`, taken from the window closest to its limit).
It is a colored speed streak whose chevron count grows with pace, followed by a
playful one-liner. Five lines per tier rotate, one every two minutes:

| Banner | Projected end-of-window usage | Reads as |
|---|---|---|
| blue `›` | under 70% | strolling: comfortable headroom |
| yellow `››` | 70–99% | sprinting: tracking to spend most of the window |
| red `›››` | 100%+ | on fire: on track to hit the limit before reset |

The on-fire banner shivers — a static bright/dim per-character buzz plus a
one-cell horizontal jitter each refresh — the most "rapid" a once-per-second
statusline can look. The blue and yellow banners are calm.

The duck is alive and well on the web: the pixel-art burn duck lives on
[milorad.io/m-statusline](https://milorad.io/m-statusline).

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
- `MESSAGES`: the five motivational lines per pace tier.
- `pace_tier()`: the strolling / sprinting / on-fire cutoffs.
- `ROTATE_SECONDS`: how often the message rotates (default 120).
- `PIPELINE`: the list of `/m` phases to track.

## Requirements

- Python 3 (standard library only).
- Claude Code with statusLine support.

## License

MIT, see [LICENSE](LICENSE).
