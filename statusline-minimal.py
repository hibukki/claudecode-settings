#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

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
    """Return (latest_cost_obs, latest_baseline) scanning in reverse."""
    latest_obs = None
    latest_baseline = None
    if not events_path.exists():
        return latest_obs, latest_baseline
    for line in iter_lines_reverse(events_path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        name = ev.get('event')
        if name == 'cost_observation' and latest_obs is None:
            latest_obs = ev.get('total_cost_usd')
        elif name == 'user_prompt_submit' and latest_baseline is None:
            latest_baseline = ev.get('baseline_cost_usd')
        if latest_obs is not None and latest_baseline is not None:
            break
    return latest_obs, latest_baseline


delta_cost = None
if session_id and cost_data.get('total_cost_usd') is not None:
    try:
        _session_dir = USAGE_STATE_DIR / session_id
        _session_dir.mkdir(parents=True, exist_ok=True)
        _events_path = _session_dir / 'events.jsonl'
        _latest_obs, _latest_baseline = read_session_state(_events_path)
        _cost_now = float(cost_data['total_cost_usd'])
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
    except Exception:
        delta_cost = None


dir_name = current_dir.rstrip('/').split('/')[-1] if current_dir else ''
branch = get_git_branch()
parts = []

if current_usage:
    cache_read = current_usage.get('cache_read_input_tokens', 0)
    cache_create = current_usage.get('cache_creation_input_tokens', 0)
    total_input = (current_usage.get('input_tokens', 0) + cache_read + cache_create)
    if total_input > 0:
        hit_pct = cache_read / total_input * 100
        if hit_pct >= 80:
            color = '\033[32m'
        elif hit_pct >= 50:
            color = '\033[33m'
        else:
            color = '\033[31m'
        parts.append(f"cache: {color}{hit_pct:.0f}%\033[0m")

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

if dir_name:
    parts.append(dir_name)

if branch:
    parts.append(f"({branch})")

ci = get_ci_status(branch)
if ci:
    parts.append(ci)

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

_render = ' | '.join(parts)
_elapsed_ms = (time.perf_counter() - _t_start) * 1000
if _elapsed_ms >= _SELF_TIMING_THRESHOLD_MS:
    _render += f" \033[90m[{int(_elapsed_ms)}ms]\033[0m"
print(_render)
