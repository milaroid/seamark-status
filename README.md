# m-statusline

A two-line [Claude Code](https://claude.com/claude-code) statusline that shows the
active model, your `/m` pipeline stage, and **pace-aware** usage bars — bars that
project where your 5-hour and weekly limits will land at reset, so an innocent-looking
60% that is on track to blow past 100% reads red *now* instead of at reset time.

Single file. Python standard library only. No dependencies.

```
Opus 4.8  ·  m implement ◉◉◐○○ 2/5
CTX ███░░░░░ 41%  ·  5H 🦆 ██░░░░░░ 23%→41% ·2h13m  ·  WK 🦆🔥 ████░░░░ 55%→109% ·3d11h
```

(In the terminal each segment is colored — green / yellow / red by load. The block
above is the plain-text shape.)

## What each segment means

**Line 1 — identity**

| Segment | Meaning |
|---|---|
| `Opus 4.8` | Active model display name. |
| `m implement ◉◉◐○○ 2/5` | Current `/m:develop` phase and progress across the pipeline. `◉` done · `◐` current · `○` pending. Hidden entirely when you are not inside an active `/m:develop` run. |

**Line 2 — metrics**

| Segment | Meaning |
|---|---|
| `CTX ███░░░░░ 41%` | Context window used. |
| `5H … 23%→41%` | 5-hour rate limit: used now → **projected** at window end. |
| `WK … 55%→109%` | 7-day rate limit: used now → projected at window end. |
| `·2h13m` | Time until that window resets. |

### The burn duck

The arrow (`used%→projected%`) and the duck come from projecting end-of-window
usage from how much of the window has already elapsed (`used% × window / elapsed`).
The faster you burn, the faster the duck runs:

| Marker | Projected end-of-window usage | Read as |
|---|---|---|
| 🦆 | under 70% | strolling — comfortable headroom |
| 🦆💨 | 70–99% | sprinting — tracking to spend most of the window |
| 🦆🔥 | 100%+ | on fire — on track to hit the limit before reset |

The duck is animated: it hops a cell forward and back between refreshes, at
whatever cadence Claude Code re-runs the statusline (`refreshInterval` in your
`statusLine` settings). Frame pairs are equal-width so the line never jitters.

The duck's pixel-art cousin lives on [milorad.io/m-statusline](https://milorad.io/m-statusline).

### Colors

Each bar and percentage is colored by load — for the rate-limit bars, by the
**projection**, not the raw used value:

| Color | Threshold |
|---|---|
| green | under 50% |
| yellow | 50–80% |
| red | 80%+ |

The projection is suppressed for the first 2% of a window, where it is just noise.

## Install

One line — downloads the script to `~/.claude/m-statusline.py` and wires the
`statusLine` block into `~/.claude/settings.json` (your existing settings are
preserved and backed up to `settings.json.bak` first):

```sh
curl -fsSL https://raw.githubusercontent.com/milorad-teodorovic/m-statusline/main/install.sh | bash
```

Prefer to read before you run? Same script, two steps:

```sh
curl -fsSL https://raw.githubusercontent.com/milorad-teodorovic/m-statusline/main/install.sh -o install.sh
less install.sh && bash install.sh
```

Restart Claude Code (or start a new session) and the duck starts running.
Re-running the installer is safe — it just refreshes the script and the
settings block.

### Manual install

No installer, no magic — two steps:

1. Drop `statusline.py` somewhere stable, e.g. `~/.claude/m-statusline.py`:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/milorad-teodorovic/m-statusline/main/statusline.py \
     -o ~/.claude/m-statusline.py
   ```

2. Point Claude Code at it in `~/.claude/settings.json`:

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 ~/.claude/m-statusline.py",
       "refreshInterval": 10
     }
   }
   ```

Either way there are no packages — the script reads the
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
it, the segment simply never appears and the rest of the statusline works unchanged —
the dependency is one-way and optional.

## Customizing

Everything tweakable lives near the top of `statusline.py`:

- `BAR_WIDTH` — width of the usage bars in cells.
- `color_for()` — the green / yellow / red thresholds.
- `pace_emoji()` — the 🧊 / 🔥 / 🚨 thresholds.
- `PIPELINE` — the list of `/m` phases to track.

## Requirements

- Python 3 (standard library only).
- Claude Code with statusLine support.

## License

MIT — see [LICENSE](LICENSE).
