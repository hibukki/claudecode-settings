#!/usr/bin/env python3
import sys
import json
import subprocess

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

dir_name = current_dir.rstrip('/').split('/')[-1] if current_dir else ''
branch = get_git_branch()
parts = []

if current_usage:
    cache_read = current_usage.get('cache_read_input_tokens', 0)
    cache_create = current_usage.get('cache_creation_input_tokens', 0)
    cache_total = cache_read + cache_create
    if cache_total > 0:
        hit_pct = cache_read / cache_total * 100
        if hit_pct >= 80:
            color = '\033[32m'
        elif hit_pct >= 50:
            color = '\033[33m'
        else:
            color = '\033[31m'
        parts.append(f"cache: {color}{hit_pct:.0f}%\033[0m")

total_cost = cost_data.get('total_cost_usd')
if total_cost is not None:
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

print(' | '.join(parts))
