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


def pace_emoji(proj):
    """Pace marker from projected end-of-window usage (ccburn convention)."""
    if proj is None:
        return ""
    if proj >= 100:
        return "🚨 "  # ahead of pace: on track to blow the limit before reset
    if proj >= 70:
        return "🔥 "  # on pace: tracking to spend most of the window
    return "🧊 "       # behind pace: comfortable headroom


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


if __name__ == "__main__":
    main()
