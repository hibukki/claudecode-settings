#!/usr/bin/env python3
"""UserPromptSubmit hook: anchor cost delta baseline.

Reads session_id from stdin, reverse-scans events.jsonl for the latest
cost_observation, appends a user_prompt_submit event embedding that cost
as baseline_cost_usd. The statusline reads this later to compute delta.

Errors are swallowed to _debug/hook-errors.log; always exits 0.
"""
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

USAGE_STATE_DIR = Path.home() / ".claude" / "usage-state"


def iter_lines_reverse(path, chunk_size=4096):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        buffer = b""
        while pos > 0:
            read_size = min(chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size) + buffer
            lines = chunk.split(b"\n")
            buffer = lines[0]
            for line in reversed(lines[1:]):
                if line:
                    yield line.decode("utf-8", errors="replace")
        if buffer:
            yield buffer.decode("utf-8", errors="replace")


def find_latest_cost(events_path):
    if not events_path.exists():
        return 0.0
    for line in iter_lines_reverse(events_path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("event") == "cost_observation":
            return float(ev.get("total_cost_usd", 0.0))
    return 0.0


def main():
    data = json.load(sys.stdin)
    session_id = data.get("session_id")
    if not session_id:
        return
    session_dir = USAGE_STATE_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    events_path = session_dir / "events.jsonl"
    baseline = find_latest_cost(events_path)
    event = {
        "v": 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "user_prompt_submit_hook",
        "event": "user_prompt_submit",
        "baseline_cost_usd": baseline,
    }
    with open(events_path, "a") as f:
        f.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            debug_dir = USAGE_STATE_DIR / "_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            with open(debug_dir / "hook-errors.log", "a") as f:
                f.write(
                    f"{datetime.now(timezone.utc).isoformat()} user-prompt-submit: "
                    f"{traceback.format_exc()}\n"
                )
        except Exception:
            pass
    sys.exit(0)
