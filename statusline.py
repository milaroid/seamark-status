#!/usr/bin/env python3
"""Claude Code statusline: model, /m pipeline stage, pace-aware usage bars.

Reads the statusLine stdin JSON (https://platform.claude.com/docs/en/statusline)
and renders two lines:

  line 1 (identity): model  ·  m stage ◉◉◐○○ 2/5
  line 2 (metrics):  CTX ████░░░░ 41%  ·  5H ██░░░░░░ 23%→41% ·2h13m  ·  WK …

Usage bars are pace-aware: the 5-hour and weekly bars project end-of-window
usage from how much of the window has already elapsed (used% x window/elapsed)
and color themselves by that projection, so a green-looking 60% that is on
track to blow past 100% reads red now instead of at reset time.
"""

import json
import os
import sys
import time

BAR_WIDTH = 8
FILLED = "█"
EMPTY = "░"
RESET = "\033[0m"
DIM = "\033[38;5;243m"
GREEN = "\033[38;5;42m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;196m"
CYAN = "\033[38;5;45m"

SEP = f"{DIM}  ·  {RESET}"
PIPELINE = ["refine", "plan", "implement", "review", "iterate"]
FIVE_HOUR = 5 * 3600
SEVEN_DAY = 7 * 86400


def color_for(pct):
    """Green under 50%, yellow 50-80%, red above 80%."""
    if pct is None:
        return DIM
    if pct >= 80:
        return RED
    if pct >= 50:
        return YELLOW
    return GREEN


def bar_cells(pct, col):
    """Render an 8-cell bar in the given color, dim for the empty remainder."""
    if pct is None:
        return f"{DIM}{EMPTY * BAR_WIDTH}{RESET}"
    pct = max(0.0, min(100.0, float(pct)))
    filled = int(round(pct / 100 * BAR_WIDTH))
    return f"{col}{FILLED * filled}{DIM}{EMPTY * (BAR_WIDTH - filled)}{RESET}"


def humanize(resets_at):
    """Compact reset countdown like ·2h13m / ·3d5h, or empty if unknown."""
    if not resets_at:
        return ""
    delta = int(resets_at) - int(time.time())
    if delta <= 0:
        return f" {DIM}·now{RESET}"
    days, rem = divmod(delta, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        txt = f"{days}d{hours}h"
    elif hours:
        txt = f"{hours}h{mins}m"
    else:
        txt = f"{mins}m"
    return f" {DIM}·{txt}{RESET}"


def project(used, resets_at, window):
    """Projected end-of-window usage from elapsed fraction, or None if too early."""
    if used is None or not resets_at:
        return None
    elapsed = window - (int(resets_at) - time.time())
    if elapsed <= window * 0.02:  # first 2% of window: projection is noise
        return None
    return min(used * window / elapsed, 999)




# ---------------------------------------------------------------------------
# Inline pixel duck: a tiny half-block sprite (2 px tall, one text row) that
# replaces a pace emoji next to each rate bar. Colored by that window's
# projection; waddles a cell per refresh; grows a flame trail when on fire.
_TIER_RGB = [(88, 164, 224), (224, 130, 60), (224, 70, 50)]  # stroll, sprint, fire
_TIER_DARK = [(58, 118, 178), (178, 100, 46), (176, 54, 40)]
_PX = {"L": (240, 150, 40), "F": (235, 95, 40), "G": (250, 200, 90),
       "E": (10, 22, 42), "o": (240, 237, 225), "W": (252, 252, 246)}
_BLANK = "\u2800"  # braille blank: empty but survives statusline line-trim


def _fg(c):
    return f"\033[38;2;{c[0]};{c[1]};{c[2]}m"


def _bg(c):
    return f"\033[48;2;{c[0]};{c[1]};{c[2]}m"


CACHE = os.path.expanduser("~/.claude/m-statusline-last.json")


def pace_emoji(proj):
    """Burn-duck pace marker; the duck waddles a cell between refreshes.

    Frame pairs are equal-width so the line never jitters.
    """
    if proj is None:
        return ""
    hop = int(time.time()) % 2
    if proj >= 100:
        # duck on fire: on track to blow the limit before reset
        return " 🦆🔥 " if hop else "🦆🔥  "
    if proj >= 70:
        # duck sprinting: tracking to spend most of the window
        return " 🦆💨 " if hop else "🦆💨  "
    # duck strolling: comfortable headroom
    return " 🦆 " if hop else "🦆  "


def big_duck_lines(proj):
    """The big duck for /m-status: the full-resolution sprite from the
    m-statusline web page (outline, wing, eye glint), rendered as half-block
    pixel art. 20 pixel rows -> 10 text rows. Colored by pace, flame when on
    fire. Returns [] when there is no projection to draw from.
    """
    if proj is None:
        return []
    tier = 2 if proj >= 100 else 1 if proj >= 70 else 0
    body = _TIER_RGB[tier]
    dark = _TIER_DARK[tier]
    hop = int(time.time()) % 2

    base = [
        "              oooooo",
        "             oBBBBBBo",
        "            oBBBBBBBBo",
        "            oBBBBBWEBo",
        "            oBBBBBBBBooooo",
        "            oBBBBBBBBoLLLLo",
        "            oBBBBBBBBooooo",
        "   oo       oBBBBBBBo",
        "  oBBo      oBBBBBBo",
        "  oBBBo    oBBBBBBBo",
        "   oBBBo  oBBBBBBBBo",
        "   oBBBBooBBBBBBBBBo",
        "    oBBBBBBBBBBBBBBo",
        "    oBBBBBBBBBBBBBBo",
        "     oBBBBBBBBBBBBo",
        "      oBBBBBBBBBBo",
        "       oooooooooo",
    ]
    wing = ["            DDDD", "          DDDDDD", "          DDDDD"]
    legs = (["         oL        oL", "        oLLo      oLLo"] if hop
            else ["            oL  oL", "           oLLooLLo"])
    flame = (["  F", " FGF", "FGGF", " FGF", "  F"] if hop
             else [" F", "FGF", " FGGFF", "FGF", " F"])

    # compose onto a 32x20 character canvas, same offsets as the web page
    W, H = 32, 20
    canvas = [["." for _ in range(W)] for _ in range(H)]

    def blit(grid, xo, yo):
        for gy, row in enumerate(grid):
            for gx, c in enumerate(row):
                if c != "." and c != " " and 0 <= yo + gy < H and 0 <= xo + gx < W:
                    canvas[yo + gy][xo + gx] = c

    blit(base, 4, 0)
    blit(wing, 4, 10 if hop else 11)
    blit(legs, 4, 17)
    if tier == 2:
        blit(flame, 3, 7)

    def px(c):
        if c == ".":
            return None
        return {"B": body, "D": dark}.get(c) or _PX.get(c, body)

    out = []
    for y in range(0, H, 2):
        cells = []
        for x in range(W):
            u, lo = px(canvas[y][x]), px(canvas[y + 1][x])
            if u and lo:
                cells.append(f"{_fg(u)}{_bg(lo)}\u2580{RESET}")
            elif u:
                cells.append(f"{_fg(u)}\u2580{RESET}")
            elif lo:
                cells.append(f"{_fg(lo)}\u2584{RESET}")
            else:
                cells.append(" ")
        out.append("".join(cells))
    return out


def limit_segment(label, obj, window):
    """A pace-aware rate-limit bar: used% -> projected%, colored by projection."""
    obj = obj or {}
    used = obj.get("used_percentage")
    resets = obj.get("resets_at")
    proj = project(used, resets, window)
    col = color_for(proj if proj is not None else used)
    cells = bar_cells(used, col)
    if used is None:
        pct = f"{DIM}--%{RESET}"
    else:
        pct = f"{col}{used:>3.0f}%{RESET}"
    arrow = f"{DIM}→{RESET}{col}{proj:.0f}%{RESET}" if proj is not None else ""
    return (f"{DIM}{label}{RESET} {pace_emoji(proj)}{cells} "
            f"{pct}{arrow}{humanize(resets)}")


def ctx_segment(data):
    pct = (data.get("context_window") or {}).get("used_percentage")
    col = color_for(pct)
    val = f"{DIM}--%{RESET}" if pct is None else f"{col}{pct:>3.0f}%{RESET}"
    return f"{DIM}CTX{RESET} {bar_cells(pct, col)} {val}"


def model_segment(data):
    name = (data.get("model") or {}).get("display_name")
    return f"{CYAN}{name}{RESET}" if name else None


def find_m_dir(cwd):
    """Walk up from cwd to the nearest .m/ holding a DEVELOP_ACTIVE marker."""
    path = os.path.abspath(cwd or os.getcwd())
    while True:
        candidate = os.path.join(path, ".m")
        if os.path.isfile(os.path.join(candidate, "DEVELOP_ACTIVE")):
            return candidate
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def read_current_phase(m_dir):
    try:
        with open(os.path.join(m_dir, "DEVELOP_ACTIVE")) as fh:
            for line in fh:
                if line.startswith("current_phase:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def mstage_segment(cwd):
    """Show the active /m:develop phase as labelled dots over the pipeline."""
    m_dir = find_m_dir(cwd)
    if not m_dir:
        return None
    phase = read_current_phase(m_dir)
    if not phase:
        return None

    def done(ph):
        return os.path.isfile(os.path.join(m_dir, f"phase-{ph}-done"))

    dots = []
    for ph in PIPELINE:
        if done(ph):
            dots.append(f"{GREEN}◉{RESET}")
        elif ph == phase:
            dots.append(f"{YELLOW}◐{RESET}")
        else:
            dots.append(f"{DIM}○{RESET}")
    completed = sum(1 for ph in PIPELINE if done(ph))
    track = "".join(dots)
    return (f"{DIM}m{RESET} {CYAN}{phase}{RESET} {track} "
            f"{DIM}{completed}/{len(PIPELINE)}{RESET}")


def join(parts):
    return SEP.join(p for p in parts if p)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    try:  # cache for /m-status (big-duck on demand)
        with open(CACHE, "w") as fh:
            json.dump(data, fh)
    except OSError:
        pass

    cwd = data.get("cwd") or (data.get("workspace") or {}).get("current_dir")
    limits = data.get("rate_limits") or {}

    identity = join([
        model_segment(data),
        mstage_segment(cwd),
    ])
    metrics = join([
        ctx_segment(data),
        limit_segment("5H", limits.get("five_hour"), FIVE_HOUR),
        limit_segment("WK", limits.get("seven_day"), SEVEN_DAY),
    ])

    lines = [ln for ln in (identity, metrics) if ln]
    sys.stdout.write("\n".join(lines))




def status_main():
    """Render the big burn duck + rate bars from the cached statusline JSON."""
    try:
        with open(CACHE) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        print("no cached statusline data yet — open a Claude Code session first")
        return
    limits = data.get("rate_limits") or {}
    fh_w = limits.get("five_hour") or {}
    sd_w = limits.get("seven_day") or {}
    projections = [
        project(fh_w.get("used_percentage"), fh_w.get("resets_at"), FIVE_HOUR),
        project(sd_w.get("used_percentage"), sd_w.get("resets_at"), SEVEN_DAY),
    ]
    worst = max((p for p in projections if p is not None), default=None)
    label = ("on fire" if worst is not None and worst >= 100
             else "sprinting" if worst is not None and worst >= 70
             else "strolling" if worst is not None else "no data")
    lines = [f"{DIM}the burn duck · {RESET}{CYAN}{label}{RESET}", ""]
    lines += big_duck_lines(worst)
    lines += ["",
              limit_segment("5H", fh_w, FIVE_HOUR),
              limit_segment("WK", sd_w, SEVEN_DAY)]
    print("\n".join(lines))


if __name__ == "__main__":
    status_main() if "--status" in sys.argv else main()
