#!/usr/bin/env python3
import sys
import json
import subprocess

# Read JSON input from Claude Code
input_data = json.load(sys.stdin)

# Extract values
current_dir = input_data.get('workspace', {}).get('current_dir', '')
transcript_path = input_data.get('transcript_path', '')

CONTEXT_WINDOW_TOKENS = 200_000
AUTOCOMPACT_BUFFER_FRACTION = 0.225
COMPACT_THRESHOLD_FRACTION = 1 - AUTOCOMPACT_BUFFER_FRACTION
# All fractions/percentages above and below are relative to total context window

def read_transcript(path):
    try:
        with open(path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except OSError:
        return []

def used_total(usage):
    if not usage:
        return 0
    return (usage.get('input_tokens', 0) +
            usage.get('output_tokens', 0) +
            usage.get('cache_read_input_tokens', 0) +
            usage.get('cache_creation_input_tokens', 0))

def is_valid_entry(entry):
    if entry.get('isSidechain') or entry.get('isApiErrorMessage'):
        return False
    msg = entry.get('message', {})
    if msg.get('role') != 'assistant':
        return False
    if 'synthetic' in str(msg.get('model', '')).lower():
        return False
    content = msg.get('content', [])
    if isinstance(content, list):
        for item in content:
            if item and item.get('type') == 'text':
                if 'no response requested' in str(item.get('text', '')).lower():
                    return False
    return used_total(msg.get('usage', {})) > 0

def get_context_usage():
    if not transcript_path:
        return None
    for line in reversed(read_transcript(transcript_path)):
        try:
            entry = json.loads(line)
            if is_valid_entry(entry):
                return entry.get('message', {}).get('usage', {})
        except json.JSONDecodeError:
            continue
    return None

def get_git_branch():
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, timeout=1
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''

# Get values
usage = get_context_usage()
dir_name = current_dir.rstrip('/').split('/')[-1] if current_dir else ''
branch = get_git_branch()

# Build output
parts = []

if usage:
    used_pct = used_total(usage) / CONTEXT_WINDOW_TOKENS * 100
    left_until_compact_pct = max(0, COMPACT_THRESHOLD_FRACTION * 100 - used_pct)
    if left_until_compact_pct <= 5:
        color = '\033[31m'  # red
    elif left_until_compact_pct <= 15:
        color = '\033[33m'  # yellow
    else:
        color = '\033[32m'  # green
    parts.append(f"{color}{left_until_compact_pct:.0f}% to compact\033[0m")

# Folder name
if dir_name:
    parts.append(dir_name)

# Git branch
if branch:
    parts.append(f"({branch})")

output = ' | '.join(parts[:2])
if len(parts) > 2:
    output += ' ' + parts[2]
print(output)
