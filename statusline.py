#!/usr/bin/env python3
"""Claude Code statusline: the m-pipeline cockpit.

Reads the statusLine stdin JSON (https://code.claude.com/docs/en/statusline)
and renders:

  line 1 (identity): model  ·  ⎇ branch ●3 ↑1  ·  ENG-142
  cockpit (while /m:develop runs):
                     m implement ◉◉◐○○ 2/5 ·12m  ·  ☐2 ✓4  ·  ⚠2
  metrics:           CTX ████░░░░ 41%  ·  5H ██░░ 23%→41% ·2h13m  ·  WK …

Usage bars are pace-aware: the 5-hour and weekly bars project end-of-window
usage from how much of the window has already elapsed (used% x window/elapsed)
so a green-looking 60% that is on track to blow past 100% reads red now. The
cockpit line is read live from the .m/ state files the /m pipeline writes.
"""

import json
import os
import re
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
CODEX_FRESH_TTL = 6 * 3600  # hide the Codex row when no run within this window


LOAD_BLUE = "\033[38;2;90;165;225m"
LOAD_GREEN = "\033[38;2;80;200;130m"
LOAD_AMBER = "\033[38;2;225;190;70m"
LOAD_RED = "\033[38;2;225;70;50m"

CLAUDE_ORANGE = "\033[38;2;230;125;34m"   # #E67D22 — Claude row label
CODEX_WHITE = "\033[38;2;255;255;255m"    # Codex row label


def color_for(pct):
    """One load ladder for every field: blue < 50, green 50-70, amber 70-90,
    red 90+. Rate bars feed it their projection, CTX its used value."""
    if pct is None:
        return DIM
    if pct >= 90:
        return LOAD_RED
    if pct >= 70:
        return LOAD_AMBER
    if pct >= 50:
        return LOAD_GREEN
    return LOAD_BLUE


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
# "To Himself" line: a Marcus Aurelius quote under the metrics, chosen by the
# 5-hour window's load and colored to match its bar — a Stoic arc that climbs
# with the burn: Start (blue) when light, Center (green) when steady, Strive
# (yellow) when pushing, Endure (red) when redlined. Rotated every two minutes.
# Text follows the public-domain George Long translation (1862), modernized.
ROTATE_SECONDS = 120

MEDITATIONS = (
    (  # Start — blue: begin, act now, mortality spurs the work
        "Confine yourself to the present.",
        "Do every act as if it were your last.",
        "No longer talk of what a good man should be. Be one.",
        "Death hangs over you; while you can, be good.",
        "Do not act as if you had ten thousand years to live.",
        "Whatever you do, do it as one who may depart at any moment.",
        "Remember how long you have put these things off.",
        "You may leave life this moment; let that govern what you do.",
        "The time any man lives is but a little.",
        "Let no act be done without purpose.",
    ),
    (  # Center — green: the inner retreat, calm, contentment
        "Nowhere can a man retreat better than into his own soul.",
        "Look within; within is the fountain of good.",
        "Whenever you wish, you can retire into yourself and be at rest.",
        "The soul is dyed by its thoughts.",
        "Very little is needed to make a happy life.",
        "Tranquility is nothing but the good ordering of the mind.",
        "Be cheerful, and need no one's help.",
        "Keep yourself pure from passion, rashness, and vanity.",
        "Be never in haste, and never slow.",
        "What suits you, O Universe, suits me.",
    ),
    (  # Strive — yellow: right action, the path, persistence
        "Always take the short road; the short road is nature's.",
        "If it is not right, do not do it; if it is not true, do not say it.",
        "The art of living is more like wrestling than dancing.",
        "Do nothing at random, but by the exact rules of the art.",
        "Do what you are about with gravity, freedom, and justice.",
        "The best revenge is not to become like your enemy.",
        "A happy lot: good inclinations, good desires, good actions.",
        "Does a man offend? It is against himself that he offends.",
        "The obstacle on the road becomes the road.",
        "Take refuge in work, and be at rest.",
    ),
    (  # Endure — red: bear it, impermanence, accept what comes
        "Be like the headland the waves break on; it stands, the sea falls still.",
        "Nothing happens to anyone that he is not formed by nature to bear.",
        "Whatever happens in the world happens justly.",
        "Take away the opinion, and the hurt is gone.",
        "Nothing that is according to nature can be evil.",
        "The universe is change; life is what our thoughts make it.",
        "You have boarded, you have sailed, you have reached the shore. Step off.",
        "In a little while you and he will both be dead.",
        "Consider how quickly all things dissolve into the whole.",
        "Time is a river of passing events; strong is its current.",
    ),
)


def quote_tier(proj):
    """Load-ladder bucket for the quote: 0 <50, 1 <70, 2 <90, 3 otherwise."""
    if proj is None:
        return None
    return 3 if proj >= 90 else 2 if proj >= 70 else 1 if proj >= 50 else 0


def meditation_line(five_hour):
    """A Marcus Aurelius line chosen by, and colored to, the 5-hour load."""
    obj = five_hour or {}
    proj = project(obj.get("used_percentage"), obj.get("resets_at"), FIVE_HOUR)
    tier = quote_tier(proj)
    if tier is None:
        return None
    pool = MEDITATIONS[tier]
    quote = pool[(int(time.time()) // ROTATE_SECONDS) % len(pool)]
    return f"{color_for(proj)}\033[3mTo Himself\033[23m: {quote}{RESET}"



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


# ---------------------------------------------------------------------------
# /m pipeline cockpit. m-statusline is the m-pipeline instrument panel: while
# /m:develop runs, a cockpit line shows the phase dots, the running phase and
# its runtime, task flow and blocker counts (and the iterate loop). When the
# pipeline is idle it stays quiet except for a small outcome badge and alerts
# (a BLOCKED last run, a stale index). Everything is read from the .m/ state
# files and learning signals m-pipeline already writes.
OUTCOMES = os.path.expanduser("~/.claude/m-learning/signals/outcomes.jsonl")
STALE_DAYS = 30


def find_m_dir(cwd):
    """Walk up from cwd to the nearest .m/ directory."""
    path = os.path.abspath(cwd or os.getcwd())
    while True:
        candidate = os.path.join(path, ".m")
        if os.path.isdir(candidate):
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


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def task_counts(m_dir):
    """(active, completed) bullet counts from TASKS.md sections."""
    text = _read(os.path.join(m_dir, "TASKS.md"))
    if not text:
        return None
    counts = {"Active": 0, "Completed": 0}
    section = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        elif line.lstrip().startswith("- ") and section in counts:
            counts[section] += 1
    return counts["Active"], counts["Completed"]


def iterate_loop(m_dir):
    """Latest 'Loop N/3: M fixed, K remaining' from PROGRESS.md, or None."""
    hits = re.findall(r"Loop (\d+)/3: \d+ fixed, (\d+) remaining",
                      _read(os.path.join(m_dir, "PROGRESS.md")))
    return hits[-1] if hits else None


def jira_key(m_dir, branch):
    """Ticket key captured from the branch via .m/jira.yml branchPattern."""
    if not branch:
        return None
    pattern = None
    for line in _read(os.path.join(m_dir, "jira.yml")).splitlines():
        if line.strip().startswith("branchPattern:"):
            pattern = line.split(":", 1)[1].strip().strip("'\"")
            # YAML double-quoted strings escape backslashes; collapse them.
            pattern = pattern.replace("\\\\", "\\")
    if not pattern:
        return None
    try:
        hit = re.search(pattern, branch)
    except re.error:
        return None
    return hit.group(1) if hit and hit.groups() else None


def last_outcomes():
    """Most recent verdict and the trailing PASSED streak from outcomes.jsonl."""
    lines = [ln for ln in _read(OUTCOMES).splitlines() if ln.strip()]
    verdicts = []
    for ln in lines:
        try:
            obj = json.loads(ln)
        except (json.JSONDecodeError, ValueError):
            continue
        if obj.get("type") == "outcome" and obj.get("verdict"):
            verdicts.append(obj["verdict"])
    if not verdicts:
        return None, 0
    streak = 0
    for v in reversed(verdicts):
        if v != "PASSED":
            break
        streak += 1
    return verdicts[-1], streak


def index_stale_days(m_dir):
    """Days since .m/INDEX.md was touched, or None if absent."""
    try:
        age = time.time() - os.path.getmtime(os.path.join(m_dir, "INDEX.md"))
    except OSError:
        return None
    return int(age // 86400)


def _read_int(path):
    """First integer in a file (the codex meter holds one number), or None."""
    try:
        with open(path, encoding="utf-8") as fh:
            return int(fh.read().strip() or 0)
    except (OSError, ValueError):
        return None


def codex_budget(m_dir):
    """token_budget from the .m/pipeline.yml codex: block, default 200000."""
    in_codex = False
    for raw in _read(os.path.join(m_dir, "pipeline.yml")).splitlines():
        stripped = raw.strip()
        if not in_codex:
            if stripped.startswith("codex:"):
                in_codex = True
            continue
        if stripped and not raw[:1].isspace():  # dedent to a top-level key ends the block
            break
        if stripped.startswith("token_budget:"):
            try:
                return int(stripped.split(":", 1)[1].split("#")[0].strip())
            except ValueError:
                return 200000
    return 200000


def codex_enabled(m_dir):
    """True when the .m/pipeline.yml codex: block has enabled: true."""
    if not m_dir:
        return False
    in_codex = False
    for raw in _read(os.path.join(m_dir, "pipeline.yml")).splitlines():
        stripped = raw.strip()
        if not in_codex:
            if stripped.startswith("codex:"):
                in_codex = True
            continue
        if stripped and not raw[:1].isspace():  # dedent to a top-level key ends the block
            break
        if stripped.startswith("enabled:"):
            return stripped.split(":", 1)[1].split("#")[0].strip().lower() == "true"
    return False


def humanize_tokens(n):
    """Compact token count like 45k / 1.4M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(n)


def codex_segment(m_dir):
    """Live Codex token burn: .m/handoff/codex-meter.txt vs the per-run budget.

    The meter file exists only while a /m Codex pass (plan/research/review) is
    burning tokens — the pipeline cleans it up at the end of every run — so the
    gauge appears during dual-engine work and stays quiet otherwise."""
    if not m_dir:
        return None
    used = _read_int(os.path.join(m_dir, "handoff", "codex-meter.txt"))
    if not used:  # absent or zero -> no burn to show
        return None
    budget = codex_budget(m_dir) or 200000
    pct = min(100.0, used / budget * 100) if budget else 0.0
    col = color_for(pct)
    return (f"{DIM}burn{RESET} {bar_cells(pct, col)} "
            f"{col}{humanize_tokens(used)}/{humanize_tokens(budget)}{RESET}")


# ---------------------------------------------------------------------------
# Codex account usage: the metered helper persists the real rate_limits the
# Codex API returns on each run to ~/.claude/.codex-limits.json. Codex reports
# two windows like Claude (a 5-hour primary and a weekly secondary, keyed by
# window_minutes), so the codex row mirrors the Claude 5H/WK bars. The snapshot
# only refreshes when a Codex run happens; between runs it shows last-known.
CODEX_LIMITS = os.path.expanduser("~/.claude/.codex-limits.json")


def codex_limits():
    """Last-known Codex rate_limits snapshot {model, ts, rate_limits}, or None."""
    try:
        with open(CODEX_LIMITS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def codex_window_label(mins):
    """Map a Codex window length to the Claude-style label (300->5H, 10080->WK)."""
    if not mins:
        return "·"
    if mins == 300:
        return "5H"
    if mins == 10080:
        return "WK"
    if mins % 1440 == 0:
        return f"{mins // 1440}D"
    return f"{mins // 60}H"


def codex_limit_segment(window):
    """A Codex usage bar: used% colored by load, with a reset countdown."""
    used = window.get("used_percent")
    label = codex_window_label(window.get("window_minutes"))
    col = color_for(used)
    pct = f"{DIM}--%{RESET}" if used is None else f"{col}{used:>3.0f}%{RESET}"
    return f"{DIM}{label}{RESET} {bar_cells(used, col)} {pct}{humanize(window.get('resets_at'))}"


def codex_usage_segments(snap):
    """The 5H/WK Codex usage bars from the snapshot, mirroring the Claude row."""
    rl = (snap or {}).get("rate_limits") or {}
    out = []
    for key in ("primary", "secondary"):
        window = rl.get(key)
        if window and window.get("used_percent") is not None:
            out.append(codex_limit_segment(window))
    return out


def codex_model_name(snap):
    """Codex model: the snapshot's model, else the global config.toml default."""
    if snap and snap.get("model"):
        return snap["model"]
    for line in _read(os.path.expanduser("~/.codex/config.toml")).splitlines():
        stripped = line.strip()
        if stripped.startswith("model") and "=" in stripped and "reasoning" not in stripped:
            return stripped.split("=", 1)[1].strip().strip("\"'")
    return "codex"


def codex_effort(snap):
    """Codex reasoning effort: the snapshot's, else config.toml model_reasoning_effort."""
    if snap and snap.get("effort"):
        return snap["effort"]
    for line in _read(os.path.expanduser("~/.codex/config.toml")).splitlines():
        stripped = line.strip()
        if stripped.startswith("model_reasoning_effort") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("\"'")
    return None


def claude_effort():
    """Claude reasoning effort from ~/.claude/settings.json effortLevel, or None."""
    try:
        with open(os.path.expanduser("~/.claude/settings.json"), encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("effortLevel")
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def model_row(name, effort, width, parts, color=DIM):
    """A metrics row: 'model · effort' in one brand color, padded to align."""
    body = join([p for p in parts if p])
    if not body:
        return None
    label = (name or "?") + (f" · {effort}" if effort else "")
    return f"{color}{label}{RESET}{' ' * max(0, width - len(label))}  {body}"


def idle_badge(m_dir):
    """Quiet idle summary: alerts loudly, brags softly, says nothing otherwise."""
    stale = index_stale_days(m_dir)
    if stale is not None and stale >= STALE_DAYS:
        return f"{YELLOW}m idx stale {stale}d{RESET}"
    verdict, _ = last_outcomes()
    if verdict == "BLOCKED":
        return f"{RED}m ✗ last run BLOCKED{RESET}"
    return None


def cockpit_line(m_dir, phase):
    """The pipeline cockpit: dots, phase + runtime, loop, tasks, blockers."""
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

    parts = [f"{DIM}m{RESET} {CYAN}{phase}{RESET} {track} "
             f"{DIM}{completed}/{len(PIPELINE)}{RESET}"]
    try:  # phase runtime from the -started marker's mtime
        started = os.path.getmtime(os.path.join(m_dir, f"phase-{phase}-started"))
        parts[0] += f" {DIM}·{humanize_secs(time.time() - started)}{RESET}"
    except OSError:
        pass
    if phase == "iterate":
        loop = iterate_loop(m_dir)
        if loop:
            n, remaining = loop
            col = GREEN if remaining == "0" else YELLOW
            parts.append(f"{col}loop {n}/3 ·{remaining} left{RESET}")
    tasks = task_counts(m_dir)
    if tasks and (tasks[0] or tasks[1]):
        done_n, total = tasks[1], tasks[0] + tasks[1]
        parts.append(f"{DIM}tasks {done_n}/{total}{RESET}")
    return join(parts)


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

    git = git_info(cwd, workspace.get("git_worktree"))
    m_dir = find_m_dir(cwd)
    phase = read_current_phase(m_dir) if m_dir else None

    ticket = jira_key(m_dir, git["branch"]) if (m_dir and git) else None
    identity = join([
        git_segment(git),
        f"{DIM}{ticket}{RESET}" if ticket else None,
        idle_badge(m_dir) if (m_dir and not phase) else None,
    ])
    cockpit = cockpit_line(m_dir, phase) if (m_dir and phase) else None
    # Two aligned, model-labeled usage rows: Claude (CTX/5H/WK) and Codex. The
    # Codex row shows its 5H/WK bars + live burn when a snapshot/meter exists,
    # and stays present throughout a /m:develop flow whenever Codex is enabled
    # (a dim idle tag between passes) — hidden only when Codex is disabled.
    claude_model = (data.get("model") or {}).get("display_name") or "claude"
    cl_eff = claude_effort()
    snap = codex_limits()
    fresh = bool(snap) and (time.time() - snap.get("ts", 0)) < CODEX_FRESH_TTL
    burn = codex_segment(m_dir)
    codex_parts = codex_usage_segments(snap) if fresh else []
    if burn:
        codex_parts.append(burn)
    develop_codex = bool(phase) and codex_enabled(m_dir)
    show_codex = bool(codex_parts) or develop_codex
    if not codex_parts and develop_codex:  # develop flow, no live pass -> idle tag
        codex_parts = [f"{DIM}· idle{RESET}"]
    codex_model = codex_model_name(snap) if show_codex else ""
    cx_eff = codex_effort(snap) if show_codex else None

    def _plen(n, e):
        return len(n) + (len(f" · {e}") if e else 0)
    label_w = max(_plen(claude_model, cl_eff), _plen(codex_model, cx_eff) if show_codex else 0, 8)

    claude_metrics = model_row(claude_model, cl_eff, label_w, [
        ctx_segment(data),
        limit_segment("5H", fh, FIVE_HOUR),
        limit_segment("WK", sd, SEVEN_DAY),
    ], CLAUDE_ORANGE)
    codex_metrics = (model_row(codex_model, cx_eff, label_w, codex_parts, CODEX_WHITE)
                     if show_codex else None)
    meditation = meditation_line(fh)

    lines = [ln for ln in (identity, cockpit, claude_metrics, codex_metrics, meditation) if ln]
    sys.stdout.write("\n".join(lines))


if __name__ == "__main__":
    main()
