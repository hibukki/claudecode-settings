#!/usr/bin/env python3
import sys
import os
import re
import json
import subprocess
import time
import zlib
import colorsys
from datetime import datetime
from urllib.parse import quote, urlsplit

_t_start = time.perf_counter()
_SELF_TIMING_THRESHOLD_MS = 1000

input_data = json.load(sys.stdin)

current_dir = input_data.get('workspace', {}).get('current_dir', '')
context_window = input_data.get('context_window', {})
context_window_size = context_window.get('context_window_size')
current_usage = context_window.get('current_usage')
scratchpad_dir = input_data.get('scratchpad_dir')


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, 'w') as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def get_git_branch():
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, timeout=1
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''

def get_pr_link(pr):
    if not pr or not pr.get('number') or not pr.get('url'):
        return ''
    return f"\033[90m\x1b]8;;{pr['url']}\x1b\\#{pr['number']}\x1b]8;;\x1b\\\033[0m"

CI_CACHE_TTL_S = 30


def ci_check_runs(sha):
    """[status, conclusion] lines from `gh api`, cached per sha for CI_CACHE_TTL_S."""
    cache_path = os.path.join(scratchpad_dir, 'statusline-ci.json') if scratchpad_dir else None
    cached = read_json(cache_path) if cache_path else None
    if cached and cached['sha'] == sha and time.time() - cached['ts'] < CI_CACHE_TTL_S:
        return cached['lines']
    result = subprocess.run(
        ['gh', 'api', f'repos/:owner/:repo/commits/{sha}/check-runs?per_page=100',
         '--jq', '.check_runs[] | [.status, (.conclusion // "")] | @tsv'],
        capture_output=True, text=True, timeout=5
    )
    lines = [l for l in result.stdout.strip().split('\n') if l] if result.returncode == 0 else []
    if cache_path:
        write_json(cache_path, {'sha': sha, 'ts': time.time(), 'lines': lines})
    return lines


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

        lines = ci_check_runs(sha)
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


def cost_since_prompt(state_path, prompt_id, cost_now):
    """Cost accrued under the current prompt. Baseline = cost seen when the previous prompt ended.
    cost_now below the baseline means the counter restarted (session resume) -> baseline 0."""
    state = read_json(state_path) or {}
    if state.get('prompt_id') == prompt_id:
        baseline = state['baseline_cost_usd']
    else:
        baseline = state.get('last_cost_usd', 0.0)
    if cost_now < baseline:
        baseline = 0.0
    write_json(state_path, {'prompt_id': prompt_id, 'baseline_cost_usd': baseline, 'last_cost_usd': cost_now})
    return cost_now - baseline


total_cost = cost_data.get('total_cost_usd')
delta_cost = None
if total_cost is not None and scratchpad_dir:
    os.makedirs(scratchpad_dir, exist_ok=True)
    delta_cost = cost_since_prompt(os.path.join(scratchpad_dir, 'statusline-cost.json'),
                                   input_data.get('prompt_id'), float(total_cost))


def project_color(name):
    """Deterministic per-name truecolor ANSI prefix. crc32 (stable, unlike hash())
    drives hue; lightness also varies so near-identical hues stay distinguishable."""
    h = zlib.crc32(name.encode() + b"1105")  # tuned salt, not arbitrary
    hue = h / 0x100000000
    light = 0.55 + (h >> 8 & 0xff) / 0xff * 0.2
    r, g, b = colorsys.hls_to_rgb(hue, light, 0.6)
    return f"\033[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m"


def make_dir_label(path):
    if not path:
        return ''
    path = path.rstrip('/')
    segs = path.split('/')
    project = segs[-1]
    suffix = ''
    # .../<project>/.claude/worktrees/<wt> → opencon/w:jolly-fermi-3293
    for i in range(len(segs) - 2):
        if (segs[i] == '.claude' and segs[i + 1] == 'worktrees'
                and i >= 1 and i + 2 < len(segs)):
            project = segs[i - 1]
            suffix = f"/w:{segs[i + 2]}"
            break
    colored = f"{project_color(project)}{project}\033[0m{suffix}"
    url = 'file://' + quote(path, safe='/')
    return f"\x1b]8;;{url}\x1b\\{colored}\x1b]8;;\x1b\\"

dir_label = make_dir_label(current_dir)
branch = get_git_branch()
parts = []

model_letter = (input_data.get('model', {}).get('display_name') or '')[:1].upper()
if model_letter:
    parts.append(f"\033[1m{model_letter}\033[0m")

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
        last_str = f"{_cache_color(hit_pct)}{hit_pct:.0f}%\033[0m"
        session_ratio = (input_data.get('prompt_cache') or {}).get('hit_ratio')
        if session_ratio is not None:
            session_pct = session_ratio * 100
            session_str = f"{_cache_color(session_pct)}{session_pct:.0f}%\033[0m"
        else:
            session_str = '\033[90m—\033[0m'
        parts.append(f"cache: {last_str},{session_str}")

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

_pr = get_pr_link(input_data.get('pr'))
if _pr:
    parts.append(_pr)

def first_prompt(transcript_path, max_lines=200):
    """The session's first user message, collapsed to one line. '' before it exists."""
    if not transcript_path or not os.path.exists(transcript_path):
        return ''
    with open(transcript_path, encoding='utf-8', errors='replace') as f:
        for _ in range(max_lines):
            line = f.readline()
            if not line:
                break
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # partially-flushed line
            if rec.get('type') != 'user' or rec.get('isSidechain') or rec.get('isMeta'):
                continue
            content = rec.get('message', {}).get('content')
            if isinstance(content, list):
                content = ' '.join(b.get('text', '') for b in content
                                   if isinstance(b, dict) and b.get('type') == 'text')
            if not isinstance(content, str):
                continue
            content = re.sub(r'<(command-[a-z]+|system-reminder|local-command-\w+)>.*?</\1>',
                             ' ', content, flags=re.S)
            content = ' '.join(content.split())
            if content:
                return content
    return ''


URL_RE = re.compile(r'https?://[^\s<>]+')
NOTION_PAGE_ID_RE = re.compile(r'-?[0-9a-f]{32}$')


def link_label(url):
    """Short label for URLs whose text is mostly noise; None = show the URL as-is."""
    parts = urlsplit(url)
    host = parts.hostname or ''
    if host == 'app.notion.com' or host == 'notion.so' or host.endswith('.notion.so'):
        slug = parts.path.rstrip('/').rsplit('/', 1)[-1]
        return NOTION_PAGE_ID_RE.sub('', slug).replace('-', ' ') or 'notion'
    if host == 'claude.ai' and '/artifact/' in parts.path:
        return 'artifact'
    return None


def shorten_links(text, max_chars):
    """text with noisy URLs replaced by OSC 8 links, truncated to max_chars visible chars."""
    segments = []  # (visible_text, url or None)
    pos = 0
    for m in URL_RE.finditer(text):
        url = m.group().rstrip('.,;:!?)')
        label = link_label(url)
        if label is None:
            continue
        segments.append((text[pos:m.start()], None))
        segments.append((label, url))
        pos = m.start() + len(url)
    segments.append((text[pos:], None))

    out = ''
    remaining = max_chars
    for visible, url in segments:
        if len(visible) > remaining:
            visible = visible[:max(remaining - 1, 0)] + '…'
        remaining -= len(visible)
        out += f"\x1b]8;;{url}\x1b\\\033[4m{visible}\033[24m\x1b]8;;\x1b\\" if url else visible
        if remaining <= 0:
            break
    return out


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

_first = first_prompt(input_data.get('transcript_path'))
if _first:
    print(f"\033[90m» {shorten_links(_first, max_chars=140)}\033[0m")
