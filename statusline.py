#!/usr/bin/env python3
import sys
import json

# Read JSON input
input_data = json.load(sys.stdin)

# Extract values
model_display = input_data.get('model', {}).get('display_name', '')
current_dir = input_data.get('workspace', {}).get('current_dir', '')
transcript_path = input_data.get('transcript_path', '')

# Context window size
CONTEXT_WINDOW = 200_000

def read_transcript(path):
    """Read and parse transcript file."""
    try:
        with open(path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def used_total(usage):
    """Calculate context tokens used (input only, cache tokens are subsets)."""
    if not usage:
        return 0
    return usage.get('input_tokens', 0)

def is_valid_entry(entry):
    """Check if entry is a valid main context entry."""
    if entry.get('isSidechain') or entry.get('isApiErrorMessage'):
        return False

    msg = entry.get('message', {})
    if msg.get('role') != 'assistant':
        return False

    model = str(msg.get('model', '')).lower()
    if 'synthetic' in model:
        return False

    content = msg.get('content', [])
    if isinstance(content, list):
        for item in content:
            if item and item.get('type') == 'text':
                text = str(item.get('text', ''))
                if 'no response requested' in text.lower():
                    return False

    usage = msg.get('usage', {})
    if used_total(usage) == 0:
        return False

    return True

def get_context_usage():
    """Get the newest main context usage from transcript."""
    if not transcript_path:
        return None

    lines = read_transcript(transcript_path)
    if not lines:
        return None

    latest_usage = None
    latest_ts = float('-inf')

    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except:
            continue

        if not is_valid_entry(entry):
            continue

        usage = entry.get('message', {}).get('usage', {})
        timestamp = entry.get('timestamp', '')

        try:
            from datetime import datetime
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
        except:
            ts = float('-inf')

        if ts > latest_ts:
            latest_ts = ts
            latest_usage = usage
        elif ts == latest_ts and used_total(usage) > used_total(latest_usage):
            latest_usage = usage

    return latest_usage

# Get context usage
usage = get_context_usage()

# Format directory name (basename)
dir_name = current_dir.rstrip('/').split('/')[-1] if current_dir else ''

# Build output
output = f"[{model_display}] 📁 {dir_name}"

if usage:
    used = used_total(usage)
    pct = (used / CONTEXT_WINDOW * 100) if CONTEXT_WINDOW > 0 else 0

    # Color based on percentage
    if pct >= 90:
        color = '\033[31m'  # red
    elif pct >= 70:
        color = '\033[33m'  # yellow
    else:
        color = '\033[32m'  # green
    reset = '\033[0m'

    output += f" | {color}{pct:.1f}%{reset}"

print(output)
