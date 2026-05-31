"""Core tracing engine — decorator, context manager, and global tracer singleton."""

from __future__ import annotations

import contextlib
import functools
import threading
import time
from typing import Any, Callable, Generator

from agent_trace.models import Span, ToolCall, Trace, TraceStatus
from agent_trace.exporters import BaseExporter, ConsoleExporter


class AgentTracer:
    """Thread-safe tracer that collects spans and tool calls into traces.

    Usage:
        tracer = AgentTracer()
        tracer.start_trace("code-review")

        with tracer.span("lint"):
            tracer.tool("terminal", {"command": "ruff check ."}).finish()

        trace = tracer.finish_trace()
        tracer.export(trace, ConsoleExporter())
    """

    def __init__(self, exporter: BaseExporter | None = None) -> None:
        self._local = threading.local()
        self._exporter = exporter or ConsoleExporter()
        self._completed_traces: list[Trace] = []

    @property
    def _current_trace(self) -> Trace | None:
        return getattr(self._local, "trace", None)

    @_current_trace.setter
    def _current_trace(self, value: Trace | None) -> None:
        self._local.trace = value

    @property
    def _span_stack(self) -> list[Span]:
        if not hasattr(self._local, "span_stack"):
            self._local.span_stack = []
        return self._local.span_stack

    # ── public API ──────────────────────────────────────────────

    def start_trace(
        self,
        name: str = "unnamed",
        model: str | None = None,
        provider: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Trace:
        trace = Trace(
            name=name,
            model=model,
            provider=provider,
            metadata=metadata or {},
        )
        self._current_trace = trace
        self._local.span_stack = []
        return trace

    def finish_trace(self, status: TraceStatus = TraceStatus.SUCCESS) -> Trace:
        trace = self._current_trace
        if trace is None:
            raise RuntimeError("No active trace — call start_trace() first")

        trace.finish(status)
        self._completed_traces.append(trace)
        self._current_trace = None
        self._local.span_stack = []
        return trace

    @contextlib.contextmanager
    def span(self, name: str, metadata: dict[str, Any] | None = None) -> Generator[Span, None, None]:
        span = Span(name=name, metadata=metadata or {})
        self._span_stack.append(span)
        try:
            yield span
        except Exception:
            span.finish(TraceStatus.ERROR)
            raise
        else:
            span.finish()
        finally:
            self._span_stack.pop()
            # Attach to parent span or directly to trace
            if self._span_stack:
                self._span_stack[-1].add_child(span)
            elif self._current_trace:
                self._current_trace.add_span(span)

    def tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolCall:
        tc = ToolCall(name=name, arguments=arguments, metadata=metadata or {})
        if self._span_stack:
            self._span_stack[-1].add_tool_call(tc)
        elif self._current_trace:
            # Direct tool call without a span
            span = Span(name=f"tool:{name}")
            span.add_tool_call(tc)
            self._current_trace.add_span(span)
        return tc

    def set_usage(self, total_tokens: int, estimated_cost_usd: float = 0.0) -> None:
        """Record token usage and cost for the current trace."""
        if self._current_trace:
            self._current_trace.total_tokens = total_tokens
            self._current_trace.estimated_cost_usd = estimated_cost_usd

    def export(self, trace: Trace, exporter: BaseExporter | None = None) -> str:
        exp = exporter or self._exporter
        return exp.export(trace)

    @property
    def completed_traces(self) -> list[Trace]:
        return list(self._completed_traces)


# ── global singleton ────────────────────────────────────────────

_global_tracer: AgentTracer | None = None
_lock = threading.Lock()


def get_tracer() -> AgentTracer:
    global _global_tracer
    if _global_tracer is None:
        with _lock:
            if _global_tracer is None:
                _global_tracer = AgentTracer()
    return _global_tracer


# ── decorator ───────────────────────────────────────────────────

def trace(
    name: str | None = None,
    track_args: bool = False,
    sanitize: list[str] | None = None,
) -> Callable:
    """Decorator that wraps a function call as a span + tool call in the global tracer.

    Args:
        name: Span name. Defaults to function name.
        track_args: If True, record function arguments as tool arguments.
        sanitize: List of argument names to redact (e.g., ['api_key', 'password']).

    Example:
        @trace(track_args=True, sanitize=["api_key"])
        def call_llm(prompt, api_key):
            ...
    """
    _sanitize = sanitize or []

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            span_name = name or func.__name__

            tool_args = None
            if track_args:
                tool_args = {k: v for k, v in kwargs.items() if k not in _sanitize}

            with tracer.span(span_name):
                tc = tracer.tool(func.__name__, arguments=tool_args)
                started = time.time()
                try:
                    result = func(*args, **kwargs)
                    tc.finish(
                        status=TraceStatus.SUCCESS,
                        result_summary=_summarize(result),
                    )
                    return result
                except Exception as e:
                    tc.finish(
                        status=TraceStatus.ERROR,
                        error_message=str(e),
                    )
                    raise

        return wrapper

    return decorator


def _summarize(value: Any, max_len: int = 200) -> str | None:
    """Create a short summary of a return value for trace output."""
    if value is None:
        return None
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s
