"""CLI for analyzing agent-trace JSON/JSONL files.

Usage:
    agent-trace stats trace.jsonl          # summary statistics
    agent-trace list trace.jsonl           # list all traces
    agent-trace show trace.jsonl <id>      # show one trace in detail
    agent-trace errors trace.jsonl         # show only failed traces
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-trace",
        description="Analyze agent-trace output files.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="Summary statistics").add_argument(
        "file", type=Path, help="Trace file (.json or .jsonl)"
    )

    sub.add_parser("list", help="List all traces").add_argument(
        "file", type=Path, help="Trace file (.json or .jsonl)"
    )

    show_p = sub.add_parser("show", help="Show a specific trace by ID")
    show_p.add_argument("file", type=Path)
    show_p.add_argument("trace_id")

    sub.add_parser("errors", help="Show only failed traces").add_argument(
        "file", type=Path, help="Trace file (.json or .jsonl)"
    )

    args = parser.parse_args()
    traces = _load_traces(args.file)

    if args.command == "stats":
        _cmd_stats(traces)
    elif args.command == "list":
        _cmd_list(traces)
    elif args.command == "show":
        _cmd_show(traces, args.trace_id)
    elif args.command == "errors":
        _cmd_errors(traces)


def _load_traces(path: Path) -> list[dict]:
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text()
    if text.strip().startswith("{"):
        return [json.loads(text)]

    traces: list[dict] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if line:
            traces.append(json.loads(line))
    return traces


def _cmd_stats(traces: list[dict]) -> None:
    total = len(traces)
    errors = sum(1 for t in traces if t.get("status") == "error")
    total_spans = sum(t.get("summary", {}).get("total_spans", 0) for t in traces)
    total_tool_calls = sum(t.get("summary", {}).get("total_tool_calls", 0) for t in traces)
    total_errors = sum(t.get("summary", {}).get("total_errors", 0) for t in traces)

    durations = [t.get("duration_ms", 0) or 0 for t in traces]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Tool call frequency
    tool_counter: Counter = Counter()
    for t in traces:
        for s in t.get("spans", []):
            for tc in s.get("tool_calls", []):
                tool_counter[tc.get("name", "unknown")] += 1

    print(f"Traces:       {total}")
    print(f"Errors:       {errors}")
    print(f"Spans:        {total_spans}")
    print(f"Tool calls:   {total_tool_calls}")
    print(f"Tool errors:  {total_errors}")
    print(f"Avg duration: {avg_duration:.0f}ms")
    print()
    print("Top tools:")
    for tool, count in tool_counter.most_common(10):
        print(f"  {tool}: {count}")


def _cmd_list(traces: list[dict]) -> None:
    for t in traces:
        status = t.get("status", "?")
        name = t.get("name", "?")
        trace_id = t.get("trace_id", "?")
        tool_calls = t.get("summary", {}).get("total_tool_calls", 0)
        dur = t.get("duration_ms") or 0
        print(f"  {trace_id}  {status:7s}  {dur:7.0f}ms  {tool_calls:3d} calls  {name}")


def _cmd_show(traces: list[dict], trace_id: str) -> None:
    for t in traces:
        if t.get("trace_id") == trace_id:
            print(json.dumps(t, indent=2, ensure_ascii=False))
            return
    print(f"Trace not found: {trace_id}", file=sys.stderr)
    sys.exit(1)


def _cmd_errors(traces: list[dict]) -> None:
    error_traces = [t for t in traces if t.get("status") == "error"]
    if not error_traces:
        print("No errors found.")
        return

    for t in error_traces:
        trace_id = t.get("trace_id", "?")
        name = t.get("name", "?")
        print(f"\n{trace_id}  {name}")
        for s in t.get("spans", []):
            for tc in s.get("tool_calls", []):
                if tc.get("status") == "error":
                    print(f"  tool:{tc.get('name')}  →  {tc.get('error_message', 'unknown')}")


if __name__ == "__main__":
    main()
