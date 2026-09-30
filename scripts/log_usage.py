#!/usr/bin/env python3
"""Append one run record to data/usage.json. The cloud routines call this at the end of a run.

Tokens are summed from the session's own Claude Code transcript when the sandbox exposes it
(~/.claude/projects/**/*.jsonl, `message.usage` on assistant entries); otherwise `tokens` is
null and `tokenSource` is "unavailable". Searches are counted from the transcript's WebSearch
calls (or taken from --searches). The last few turns after this runs are not counted.

  python3 scripts/log_usage.py --deck news --model claude-sonnet-5 \
      --started 2026-09-30T01:31:00Z --stories 46
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "usage.json")
KEEP = 60
IST = timezone(timedelta(hours=5, minutes=30))


def newest_transcript():
    roots = [os.path.expanduser("~/.claude/projects")]
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        roots.insert(0, os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "projects"))
    files = []
    for r in roots:
        files += glob.glob(os.path.join(r, "**", "*.jsonl"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None


def summarize(path):
    # One assistant message is written as several lines that repeat the same id and usage,
    # so keep usage once per message id; count WebSearch calls once per tool_use id.
    usage, searches = {}, set()
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") != "assistant":
                continue
            m = e.get("message") or {}
            mid = m.get("id") or e.get("uuid")
            if mid and isinstance(m.get("usage"), dict):
                usage[mid] = m["usage"]
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "WebSearch":
                    searches.add(b.get("id") or json.dumps(b.get("input"), sort_keys=True))
    if not usage:
        return None, len(searches)
    t = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    for u in usage.values():
        t["input"] += int(u.get("input_tokens") or 0)
        t["output"] += int(u.get("output_tokens") or 0)
        t["cacheRead"] += int(u.get("cache_read_input_tokens") or 0)
        t["cacheWrite"] += int(u.get("cache_creation_input_tokens") or 0)
    t["total"] = t["input"] + t["output"] + t["cacheRead"] + t["cacheWrite"]
    t["turns"] = len(usage)
    return t, len(searches)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", required=True)
    ap.add_argument("--model", default="")
    ap.add_argument("--started", default="", help="run start, ISO 8601 UTC")
    ap.add_argument("--stories", type=int, default=0)
    ap.add_argument("--searches", type=int, default=None, help="fallback if no transcript")
    ap.add_argument("--transcript", default=None)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    tokens, searches = None, None
    path = a.transcript or newest_transcript()
    if path:
        try:
            tokens, searches = summarize(path)
        except OSError as ex:
            print("transcript unreadable:", ex, file=sys.stderr)
    duration = None
    if a.started:
        try:
            duration = int((now - datetime.fromisoformat(a.started.replace("Z", "+00:00"))).total_seconds())
        except ValueError:
            pass

    rec = {"date": datetime.now(IST).strftime("%Y-%m-%d"), "deck": a.deck, "model": a.model,
           "startedAt": a.started, "finishedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "durationSec": duration, "searches": searches if tokens is not None else a.searches,
           "stories": a.stories,
           "tokens": tokens, "tokenSource": "transcript" if tokens else "unavailable"}
    try:
        runs = json.load(open(a.out, encoding="utf-8"))
        if not isinstance(runs, list):
            runs = []
    except (OSError, ValueError):
        runs = []
    runs = (runs + [rec])[-KEEP:]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("usage logged: %s, %s tokens (%s), %s searches, %s stories"
          % (a.deck, tokens["total"] if tokens else "no", rec["tokenSource"], rec["searches"], a.stories))


if __name__ == "__main__":
    main()
