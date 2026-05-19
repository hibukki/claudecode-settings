#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

_t_start = time.perf_counter()
_SELF_TIMING_THRESHOLD_MS = 1000
USAGE_STATE_DIR = Path.home() / ".claude" / "usage-state"

input_data = json.load(sys.stdin)

current_dir = input_data.get('workspace', {}).get('current_dir', '')
context_window = input_data.get('context_window', {})
context_window_size = context_window.get('context_window_size')
current_usage = context_window.get('current_usage')

def get_git_branch():
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, timeout=1
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''

def get_pr_link(branch):
    if not branch:
        return ''
    try:
        result = subprocess.run(
            ['gh', 'pr', 'view', '--json', 'number,url'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            return ''
        data = json.loads(result.stdout)
        number = data.get('number')
        url = data.get('url')
        if not number or not url:
            return ''
        return f"\033[90m\x1b]8;;{url}\x1b\\#{number}\x1b]8;;\x1b\\\033[0m"
    except Exception:
        return ''

def get_ci_status(branch):
    if not branch:
        return ''
    try:
        sha_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=1
        )
        if sha_result.returncode != 0:
            return ''
        sha = sha_result.stdout.strip()

        result = subprocess.run(
            ['gh', 'api', f'repos/:owner/:repo/commits/{sha}/check-runs?per_page=100',
             '--jq', '.check_runs[] | [.status, (.conclusion // "")] | @tsv'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return ''
        lines = [l for l in result.stdout.strip().split('\n') if l]
        if not lines:
            return ''

        GREEN = '\033[32m'
        RED = '\033[31m'
        GRAY = '\033[90m'
        YELLOW = '\033[33m'
        RST = '\033[0m'

        n_pass = n_fail = n_skip = n_running = 0
        for line in lines:
            cols = line.split('\t')
            status = cols[0] if cols else ''
            conclusion = cols[1] if len(cols) > 1 else ''
            if status != 'completed':
                n_running += 1
            elif conclusion == 'success':
                n_pass += 1
            elif conclusion in ('skipped', 'neutral'):
                n_skip += 1
            else:
                n_fail += 1
        total = len(lines)

        # CI:3,1,2/5  (green pass, red fail, gray skip / total)
        parts = [f'{GREEN}{n_pass}{RST}']
        if n_fail:
            parts.append(f'{RED}{n_fail}{RST}')
        if n_skip:
            parts.append(f'{GRAY}{n_skip}{RST}')
        ci = 'CI:' + ','.join(parts) + f'/{total}'
        if n_running:
            ci += f'{YELLOW}…{RST}'
        return ci
    except Exception:
        return ''

cost_data = input_data.get('cost', {})
session_id = input_data.get('session_id')


def iter_lines_reverse(path, chunk_size=4096):
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        buffer = b''
        while pos > 0:
            read_size = min(chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size) + buffer
            lines = chunk.split(b'\n')
            buffer = lines[0]
            for line in reversed(lines[1:]):
                if line:
                    yield line.decode('utf-8', errors='replace')
        if buffer:
            yield buffer.decode('utf-8', errors='replace')


def read_session_state(events_path):
    """Return (latest_cost_obs, latest_baseline, turn_end_usages_since_ups).

    `turn_end_usages_since_ups` lists every turn_end event newer than the
    latest user_prompt_submit. Scanning stops once the ups boundary is found
    AND the latest cost_observation has been located.
    """
    latest_obs = None
    latest_baseline = None
    usages = []
    seen_ups = False
    if not events_path.exists():
        return latest_obs, latest_baseline, usages
    for line in iter_lines_reverse(events_path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        name = ev.get('event')
        if name == 'cost_observation' and latest_obs is None:
            latest_obs = ev.get('total_cost_usd')
        elif name == 'user_prompt_submit' and not seen_ups:
            latest_baseline = ev.get('baseline_cost_usd')
            seen_ups = True
        elif name == 'turn_end' and not seen_ups:
            u = ev.get('usage')
            if u:
                usages.append(u)
        if latest_obs is not None and seen_ups:
            break
    return latest_obs, latest_baseline, usages


delta_cost = None
cache_pct_since_ups = None
if session_id:
    try:
        _session_dir = USAGE_STATE_DIR / session_id
        _session_dir.mkdir(parents=True, exist_ok=True)
        _events_path = _session_dir / 'events.jsonl'
        _latest_obs, _latest_baseline, _usages = read_session_state(_events_path)
        _cost_now = cost_data.get('total_cost_usd')
        if _cost_now is not None:
            _cost_now = float(_cost_now)
            if _latest_obs is None or abs(float(_latest_obs) - _cost_now) > 1e-9:
                _ev = {
                    'v': 1,
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'source': 'statusline',
                    'event': 'cost_observation',
                    'total_cost_usd': _cost_now,
                }
                with open(_events_path, 'a') as _f:
                    _f.write(json.dumps(_ev) + '\n')
            if _latest_baseline is not None:
                delta_cost = _cost_now - float(_latest_baseline)
        if _usages:
            _cr = sum(u.get('cache_read_input_tokens', 0) for u in _usages)
            _cc = sum(u.get('cache_creation_input_tokens', 0) for u in _usages)
            _it = sum(u.get('input_tokens', 0) for u in _usages)
            _tot = _cr + _cc + _it
            if _tot > 0:
                cache_pct_since_ups = _cr / _tot * 100
    except Exception:
        delta_cost = None
        cache_pct_since_ups = None


def make_dir_label(path):
    if not path:
        return ''
    path = path.rstrip('/')
    segs = path.split('/')
    label = segs[-1]
    # .../<project>/.claude/worktrees/<wt> → opencon/w:jolly-fermi-3293
    for i in range(len(segs) - 2):
        if (segs[i] == '.claude' and segs[i + 1] == 'worktrees'
                and i >= 1 and i + 2 < len(segs)):
            label = f"{segs[i - 1]}/w:{segs[i + 2]}"
            break
    url = 'file://' + quote(path, safe='/')
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"

dir_label = make_dir_label(current_dir)
branch = get_git_branch()
parts = []

def get_session_resources():
    """RSS bytes + CPU% for this CC session (parent process + its descendants).

    Walks the process tree rooted at our parent (the `claude` process), which
    covers MCP servers, subagents, hook scripts, and bash subprocesses spawned
    by this session. One `ps` call total.
    """
    try:
        ppid = os.getppid()
        result = subprocess.run(
            ['ps', '-Ao', 'pid=,ppid=,rss=,pcpu='],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            return None
        children = {}
        info = {}
        for line in result.stdout.splitlines():
            cols = line.split()
            if len(cols) < 4:
                continue
            try:
                pid = int(cols[0]); pp = int(cols[1])
                rss_kb = int(cols[2]); cpu = float(cols[3])
            except ValueError:
                continue
            children.setdefault(pp, []).append(pid)
            info[pid] = (rss_kb, cpu)
        total_rss_kb = 0
        total_cpu = 0.0
        stack = [ppid]
        seen = set()
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            if p in info:
                r, c = info[p]
                total_rss_kb += r
                total_cpu += c
            stack.extend(children.get(p, []))
        return total_rss_kb * 1024, total_cpu
    except Exception:
        return None


def format_resources(stats):
    if not stats:
        return ''
    rss_bytes, cpu = stats
    gb = rss_bytes / (1024 ** 3)
    if gb >= 1:
        ram_str = f"{gb:.1f}G"
    else:
        ram_str = f"{rss_bytes / (1024 ** 2):.0f}M"
    return f"\033[90m{ram_str} {cpu:.0f}%\033[0m"


def _cache_color(pct):
    if pct >= 80:
        return '\033[32m'
    if pct >= 50:
        return '\033[33m'
    return '\033[31m'


if current_usage:
    cache_read = current_usage.get('cache_read_input_tokens', 0)
    cache_create = current_usage.get('cache_creation_input_tokens', 0)
    total_input = (current_usage.get('input_tokens', 0) + cache_read + cache_create)
    if total_input > 0:
        hit_pct = cache_read / total_input * 100
        last_col = _cache_color(hit_pct)
        last_str = f"{last_col}{hit_pct:.0f}%\033[0m"
        if cache_pct_since_ups is not None:
            ups_col = _cache_color(cache_pct_since_ups)
            ups_str = f"{ups_col}{cache_pct_since_ups:.0f}%\033[0m"
        else:
            ups_str = '\033[90m—\033[0m'
        parts.append(f"cache: {last_str},{ups_str}")

total_cost = cost_data.get('total_cost_usd')
if total_cost is not None:
    if delta_cost is not None:
        parts.append(f"${total_cost:.2f},${delta_cost:.2f}")
    else:
        parts.append(f"${total_cost:.2f}")

if current_usage and context_window_size:
    used = (current_usage.get('input_tokens', 0) +
            current_usage.get('output_tokens', 0) +
            current_usage.get('cache_read_input_tokens', 0) +
            current_usage.get('cache_creation_input_tokens', 0))
    used_pct = used / context_window_size * 100
    if used_pct >= 80:
        color = '\033[31m'   # red
    elif used_pct >= 60:
        color = '\033[33m'   # yellow
    else:
        color = '\033[32m'   # green
    parts.append(f"{color}{used_pct:.0f}% used\033[0m")

if dir_label:
    parts.append(dir_label)

ci = get_ci_status(branch)
if ci:
    parts.append(ci)

_pr = get_pr_link(branch)
if _pr:
    parts.append(_pr)

def format_reset_time(epoch, short=False):
    dt = datetime.fromtimestamp(epoch)
    hour = dt.strftime('%-I%p').lower()
    if short:
        return hour
    return dt.strftime('%a ') + hour

rate_limits = input_data.get('rate_limits', {})
five_h = rate_limits.get('five_hour', {})
seven_d = rate_limits.get('seven_day', {})

def time_elapsed_pct(resets_at, window_seconds):
    if not resets_at:
        return None
    now = datetime.now().timestamp()
    window_start = resets_at - window_seconds
    elapsed = now - window_start
    return max(0, min(100, elapsed / window_seconds * 100))

def burn_rate(used_pct, time_pct):
    if time_pct is None or time_pct < 0.05:
        return None
    return used_pct / time_pct

def format_rate(rate):
    if rate is None:
        return ''
    if rate >= 2:
        color = '\033[31m'
    elif rate >= 1.2:
        color = '\033[33m'
    else:
        color = '\033[32m'
    return f"/{color}{rate:.1f}x\033[0m"

if five_h.get('used_percentage') is not None:
    pct = round(five_h['used_percentage'])
    reset = format_reset_time(five_h['resets_at'], short=True) if five_h.get('resets_at') else ''
    t_pct = time_elapsed_pct(five_h.get('resets_at'), 5 * 3600)
    rate = burn_rate(five_h['used_percentage'], t_pct)
    r_str = format_rate(rate)
    parts.append(f"{pct}%{r_str}/{reset}" if reset else f"{pct}%{r_str}")

if seven_d.get('used_percentage') is not None:
    pct = round(seven_d['used_percentage'])
    reset = format_reset_time(seven_d['resets_at'], short=False) if seven_d.get('resets_at') else ''
    t_pct = time_elapsed_pct(seven_d.get('resets_at'), 7 * 24 * 3600)
    rate = burn_rate(seven_d['used_percentage'], t_pct)
    r_str = format_rate(rate)
    parts.append(f"{pct}%{r_str}/{reset}" if reset else f"{pct}%{r_str}")

_res = format_resources(get_session_resources())
if _res:
    parts.append(_res)

_render = ' | '.join(parts)
_elapsed_ms = (time.perf_counter() - _t_start) * 1000
if _elapsed_ms >= _SELF_TIMING_THRESHOLD_MS:
    _render += f" \033[90m[{int(_elapsed_ms)}ms]\033[0m"
print(_render)
