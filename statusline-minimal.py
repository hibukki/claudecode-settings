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
            ['gh', 'run', 'list', '--commit', sha,
             '--json', 'status,conclusion,name', '--limit', '20'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            return ''
        runs = json.loads(result.stdout)
        if not runs:
            return ''

        GREEN = '\033[32m'
        RED = '\033[31m'
        GRAY = '\033[90m'
        YELLOW = '\033[33m'
        RST = '\033[0m'

        n_pass = sum(1 for r in runs if r.get('conclusion') == 'success')
        n_fail = sum(1 for r in runs if r.get('status') == 'completed' and r.get('conclusion') not in ('success', 'skipped', ''))
        n_skip = sum(1 for r in runs if r.get('conclusion') == 'skipped')
        n_running = sum(1 for r in runs if r.get('status') != 'completed')
        total = len(runs)

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

dir_name = current_dir.rstrip('/').split('/')[-1] if current_dir else ''
branch = get_git_branch()
parts = []

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
