"""Core data models for agent traces."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TraceStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolCall:
    """A single tool call made by an AI agent."""

    name: str
    arguments: dict[str, Any] | None = None
    result_summary: str | None = None
    status: TraceStatus = TraceStatus.SUCCESS

    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    duration_ms: float | None = None

    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(
        self,
        status: TraceStatus = TraceStatus.SUCCESS,
        result_summary: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.finished_at = time.time()
        self.duration_ms = (self.finished_at - self.started_at) * 1000
        self.status = status
        self.result_summary = result_summary
        if error_message:
            self.error_message = error_message

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class Span:
    """A named span within a trace — groups related tool calls."""

    name: str
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    duration_ms: float | None = None

    status: TraceStatus = TraceStatus.SUCCESS
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    children: list[Span] = field(default_factory=list)

    def finish(self, status: TraceStatus = TraceStatus.SUCCESS) -> None:
        self.finished_at = time.time()
        self.duration_ms = (self.finished_at - self.started_at) * 1000
        self.status = status

    def add_tool_call(self, tc: ToolCall) -> None:
        self.tool_calls.append(tc)

    def add_child(self, span: Span) -> None:
        self.children.append(span)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "status": self.status.value,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "children": [child.to_dict() for child in self.children],
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    """Top-level trace — represents a full agent session or task."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "unnamed"

    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    duration_ms: float | None = None

    status: TraceStatus = TraceStatus.SUCCESS
    spans: list[Span] = field(default_factory=list)

    model: str | None = None
    provider: str | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: TraceStatus = TraceStatus.SUCCESS) -> None:
        self.finished_at = time.time()
        self.duration_ms = (self.finished_at - self.started_at) * 1000
        self.status = status

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    def to_dict(self) -> dict[str, Any]:
        tool_count = sum(len(s.tool_calls) for s in self.spans)
        error_count = sum(
            1 for s in self.spans for tc in s.tool_calls if tc.status == TraceStatus.ERROR
        )
        return {
            "trace_id": self.id,
            "name": self.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "status": self.status.value,
            "model": self.model,
            "provider": self.provider,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "spans": [s.to_dict() for s in self.spans],
            "summary": {
                "total_spans": len(self.spans),
                "total_tool_calls": tool_count,
                "total_errors": error_count,
            },
            "metadata": self.metadata,
        }
