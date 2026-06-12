#!/usr/bin/env python3
"""Claude Code statusline: model, git, /m stage, pace-aware usage, forecast.

Reads the statusLine stdin JSON (https://code.claude.com/docs/en/statusline)
and renders three lines:

  line 1 (identity): model  ·  ⎇ branch ●3 ↑1  ·  m stage ◉◉◐○○ 2/5
  line 2 (metrics):  CTX ████░░░░ 41%  ·  5H ██░░ 23%→41% ·2h13m  ·  WK …
  line 3 (forecast): → WK cap ~6h  ·  ›››toasty

Usage bars are pace-aware: the 5-hour and weekly bars project end-of-window
usage from how much of the window has already elapsed (used% x window/elapsed)
so a green-looking 60% that is on track to blow past 100% reads red now. The
forecast line turns that projection into a verdict — time until you hit the
limit at the current rate — plus a one-word pace tag.
"""

import json
import os
import subprocess
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
    return f" {DIM}·{humanize_secs(int(resets_at) - time.time())}{RESET}"


def humanize_secs(secs):
    """Duration like 6h · 45m · 2d3h."""
    secs = max(0, int(secs))
    if secs < 60:
        return "now"
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return f"{days}d{hours}h"
    if hours:
        return f"{hours}h{mins}m"
    return f"{mins}m"


def project(used, resets_at, window):
    """Projected end-of-window usage from elapsed fraction, or None if too early."""
    if used is None or not resets_at:
        return None
    elapsed = window - (int(resets_at) - time.time())
    if elapsed <= window * 0.02:  # first 2% of window: projection is noise
        return None
    return min(used * window / elapsed, 999)


# ---------------------------------------------------------------------------
# Git segment: branch + worktree + dirty/ahead/behind, read by running git in
# the current directory (the statusLine JSON carries no current-branch field).
# Results are cached on disk per cwd so the once-per-second refresh does not
# spawn a fresh fistful of subprocesses every tick.
GIT_CACHE = os.path.expanduser("~/.claude/.m-statusline-gitcache.json")
GIT_TTL = 5


def _git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd, *args],
                             capture_output=True, text=True, timeout=1.0)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _compute_git(cwd, worktree):
    branch = _git(cwd, "symbolic-ref", "--short", "HEAD")
    detached = False
    if branch is None:
        branch = _git(cwd, "rev-parse", "--short", "HEAD")
        if branch is None:
            return None  # not a git repo
        detached = True
    porcelain = _git(cwd, "status", "--porcelain")
    dirty = len([ln for ln in porcelain.splitlines() if ln.strip()]) if porcelain else 0
    ahead = behind = 0
    lr = _git(cwd, "rev-list", "--count", "--left-right", "@{u}...HEAD")
    if lr and "\t" in lr:
        left, right = lr.split("\t")[:2]
        behind, ahead = int(left or 0), int(right or 0)
    return {"branch": branch, "detached": detached, "dirty": dirty,
            "ahead": ahead, "behind": behind, "worktree": worktree}


def git_info(cwd, worktree):
    """Cached git state for cwd, recomputed at most once per GIT_TTL seconds."""
    if not cwd:
        return None
    now = time.time()
    cache = {}
    try:
        with open(GIT_CACHE) as fh:
            cache = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    entry = cache.get(cwd)
    if entry and now - entry["ts"] < GIT_TTL:
        return entry["data"]
    data = _compute_git(cwd, worktree)
    cache[cwd] = {"ts": now, "data": data}
    try:
        with open(GIT_CACHE, "w") as fh:
            json.dump(cache, fh)
    except OSError:
        pass
    return data


def git_segment(info):
    """⎇ branch with worktree label and dirty/ahead/behind counters."""
    if not info:
        return None
    head = (f"{DIM}⎇ {info['branch']}{RESET}" if info["detached"]
            else f"{CYAN}⎇ {info['branch']}{RESET}")
    extra = []
    if info.get("worktree"):
        extra.append(f"{DIM}⌂{info['worktree']}{RESET}")
    if info["dirty"]:
        extra.append(f"{YELLOW}●{info['dirty']}{RESET}")
    if info["ahead"]:
        extra.append(f"{GREEN}↑{info['ahead']}{RESET}")
    if info["behind"]:
        extra.append(f"{RED}↓{info['behind']}{RESET}")
    return head + ((" " + " ".join(extra)) if extra else "")


# ---------------------------------------------------------------------------
# Forecast line: a verdict (time until you hit a limit at the current rate)
# plus a one-word pace tag. Three tiers: strolling (blue) < 70, sprinting
# (yellow) 70-99, on fire (red) 100+. Tags rotate one every two minutes.
TIER_BLUE = "\033[38;2;90;165;225m"
TIER_YELLOW = "\033[38;2;225;190;70m"
TIER_RED = "\033[38;2;225;70;50m"
TIER_COLORS = (TIER_BLUE, TIER_YELLOW, TIER_RED)
ROTATE_SECONDS = 120

TAGS = (
    ("chill", "cruisin", "breezy"),
    ("pushing", "toasty", "warm"),
    ("blazing", "cooked", "mayday"),
)


def pace_tier(proj):
    """0 strolling (<70), 1 sprinting (70-99), 2 on fire (100+); None if unknown."""
    if proj is None:
        return None
    return 2 if proj >= 100 else 1 if proj >= 70 else 0


def pace_tag(tier):
    """Tier-colored speed streak + one rotating word."""
    word = TAGS[tier][(int(time.time()) // ROTATE_SECONDS) % len(TAGS[tier])]
    return f"{TIER_COLORS[tier]}{'›' * (tier + 1)}{word}{RESET}"


def forecast_line(windows):
    """`→ <verdict> · ›››tag` from the worst projection, or None when no data."""
    worst = None
    soonest_cap = None     # (label, seconds-to-100%)
    soonest_reset = None   # (label, seconds-to-reset)
    for label, obj, window in windows:
        obj = obj or {}
        used = obj.get("used_percentage")
        resets = obj.get("resets_at")
        proj = project(used, resets, window)
        if proj is None:
            continue
        worst = proj if worst is None else max(worst, proj)
        if resets:
            secs = int(resets) - time.time()
            if soonest_reset is None or secs < soonest_reset[1]:
                soonest_reset = (label, secs)
            if proj >= 100 and used:
                elapsed = window - secs
                ttc = (100 - used) * elapsed / used
                if soonest_cap is None or ttc < soonest_cap[1]:
                    soonest_cap = (label, ttc)
    tier = pace_tier(worst)
    if tier is None:
        return None
    if soonest_cap:
        verdict = (f"{TIER_RED}{soonest_cap[0]} cap ~"
                   f"{humanize_secs(soonest_cap[1])}{RESET}")
    elif soonest_reset:
        col = TIER_YELLOW if tier == 1 else TIER_BLUE
        word = "tight" if tier == 1 else "clear"
        verdict = (f"{col}{word} · {soonest_reset[0]} resets "
                   f"{humanize_secs(soonest_reset[1])}{RESET}")
    else:
        verdict = f"{TIER_COLORS[tier]}on pace{RESET}"
    return f"{DIM}→{RESET} {verdict}{SEP}{pace_tag(tier)}"


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
    return f"{DIM}{label}{RESET} {cells} {pct}{arrow}{humanize(resets)}"


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

    workspace = data.get("workspace") or {}
    cwd = data.get("cwd") or workspace.get("current_dir")
    limits = data.get("rate_limits") or {}
    fh = limits.get("five_hour") or {}
    sd = limits.get("seven_day") or {}

    identity = join([
        model_segment(data),
        git_segment(git_info(cwd, workspace.get("git_worktree"))),
        mstage_segment(cwd),
    ])
    metrics = join([
        ctx_segment(data),
        limit_segment("5H", fh, FIVE_HOUR),
        limit_segment("WK", sd, SEVEN_DAY),
    ])
    forecast = forecast_line([("5H", fh, FIVE_HOUR), ("WK", sd, SEVEN_DAY)])

    lines = [ln for ln in (identity, metrics, forecast) if ln]
    sys.stdout.write("\n".join(lines))


if __name__ == "__main__":
    main()
