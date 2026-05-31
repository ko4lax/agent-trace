"""Exporters — format and output traces as JSON, JSONL, or console output."""

from __future__ import annotations

import abc
import json
import sys
from datetime import datetime, timezone
from typing import Any

from agent_trace.models import Trace, TraceStatus


class BaseExporter(abc.ABC):
    """Abstract base for trace exporters."""

    @abc.abstractmethod
    def export(self, trace: Trace) -> str:
        ...


class JSONExporter(BaseExporter):
    """Export a single trace as pretty-printed JSON."""

    def __init__(self, indent: int = 2) -> None:
        self.indent = indent

    def export(self, trace: Trace) -> str:
        return json.dumps(trace.to_dict(), indent=self.indent, ensure_ascii=False)


class JSONLExporter(BaseExporter):
    """Export a trace as a single newline-delimited JSON line.

    Useful for streaming traces to log files or piped analysis pipelines.
    """

    def export(self, trace: Trace) -> str:
        return json.dumps(trace.to_dict(), ensure_ascii=False) + "\n"


class ConsoleExporter(BaseExporter):
    """Human-readable console output with colors (when available)."""

    HEADER = "\033[1;36m"  # bold cyan
    DIM = "\033[2m"        # dim
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        self.use_color = use_color and sys.stdout.isatty()

    def export(self, trace: Trace) -> str:
        lines: list[str] = []

        duration = f"{trace.duration_ms:.0f}ms" if trace.duration_ms else "in progress"
        status_icon = self._status_icon(trace.status)

        lines.append(self._c(f"╭─ Trace: {trace.name}  {status_icon}  {duration}", self.HEADER))
        lines.append(self._c(f"├  ID: {trace.id}", self.DIM))

        if trace.model:
            model_info = f"{trace.provider or ''}/{trace.model}".strip("/")
            lines.append(self._c(f"├  Model: {model_info}", self.DIM))

        if trace.total_tokens:
            cost = f"  ${trace.estimated_cost_usd:.4f}" if trace.estimated_cost_usd else ""
            lines.append(self._c(f"├  Tokens: {trace.total_tokens:,}{cost}", self.DIM))

        for i, span in enumerate(trace.spans):
            is_last_span = i == len(trace.spans) - 1
            prefix = "└" if is_last_span else "├"
            span_dur = f"{span.duration_ms:.0f}ms" if span.duration_ms else "..."

            lines.append(self._c(f"{prefix}─ Span: {span.name}  {self._status_icon(span.status)}  {span_dur}", self.DIM))

            for j, tc in enumerate(span.tool_calls):
                is_last_tc = j == len(span.tool_calls) - 1
                tc_prefix = "    └" if is_last_tc else "    ├"
                tc_dur = f"  {tc.duration_ms:.0f}ms" if tc.duration_ms else ""

                status = self._status_icon(tc.status)
                lines.append(f"{tc_prefix}─ tool:{tc.name}{tc_dur}  {status}")

                if tc.status == TraceStatus.ERROR and tc.error_message:
                    lines.append(self._c(f"         error: {tc.error_message}", self.RED))

                if tc.result_summary:
                    lines.append(self._c(f"         → {tc.result_summary}", self.DIM))

        return "\n".join(lines)

    def _c(self, text: str, color: str) -> str:
        if self.use_color:
            return f"{color}{text}{self.RESET}"
        return text

    @staticmethod
    def _status_icon(status: TraceStatus) -> str:
        return {
            TraceStatus.SUCCESS: "✓",
            TraceStatus.ERROR: "✗",
            TraceStatus.TIMEOUT: "⏱",
            TraceStatus.CANCELLED: "⊘",
        }.get(status, "?")
