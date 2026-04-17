#!/usr/bin/env python3
"""Stop hook: emit turn_end events for new assistant turns in this user-message window.

Reads session_id and transcript_path from stdin. Finds the latest
user_prompt_submit in events.jsonl and the set of requestIds already logged
as turn_end since that event. Walks the transcript for assistant lines
newer than that user_prompt_submit (skipping isSidechain), and appends one
turn_end event per new requestId with its message.usage.

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


def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def find_turn_context(events_path):
    """Return (ups_dt, seen_request_ids) for the current user-message turn."""
    if not events_path.exists():
        return None, set()
    seen = set()
    for line in iter_lines_reverse(events_path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        name = ev.get("event")
        if name == "user_prompt_submit":
            return parse_iso(ev.get("ts")), seen
        if name == "turn_end":
            rid = ev.get("requestId")
            if rid:
                seen.add(rid)
    return None, seen


def main():
    data = json.load(sys.stdin)
    session_id = data.get("session_id")
    transcript_path = data.get("transcript_path")
    if not session_id or not transcript_path:
        return
    session_dir = USAGE_STATE_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    events_path = session_dir / "events.jsonl"

    ups_dt, seen_rids = find_turn_context(events_path)

    transcript = Path(transcript_path).expanduser()
    if not transcript.exists():
        return

    new_events = []
    emitted = set(seen_rids)
    with open(transcript) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("type") != "assistant":
                continue
            if entry.get("isSidechain"):
                continue
            ts = parse_iso(entry.get("timestamp"))
            if ups_dt is not None and ts is not None and ts <= ups_dt:
                continue
            rid = entry.get("requestId")
            if not rid or rid in emitted:
                continue
            usage = (entry.get("message") or {}).get("usage")
            if not usage:
                continue
            emitted.add(rid)
            new_events.append({
                "v": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "stop_hook",
                "event": "turn_end",
                "requestId": rid,
                "usage": {
                    "input_tokens": usage.get("input_tokens", 0),
                    "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                    "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                },
            })

    if new_events:
        with open(events_path, "a") as f:
            for ev in new_events:
                f.write(json.dumps(ev) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            debug_dir = USAGE_STATE_DIR / "_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            with open(debug_dir / "hook-errors.log", "a") as f:
                f.write(
                    f"{datetime.now(timezone.utc).isoformat()} stop: "
                    f"{traceback.format_exc()}\n"
                )
        except Exception:
            pass
    sys.exit(0)
