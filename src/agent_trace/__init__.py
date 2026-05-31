"""agent_trace — Framework-agnostic observability for AI coding agents."""

from agent_trace.models import Trace, Span, ToolCall, TraceStatus
from agent_trace.tracer import AgentTracer, trace, get_tracer
from agent_trace.exporters import JSONExporter, JSONLExporter, ConsoleExporter

__version__ = "0.1.0"
__all__ = [
    "Trace",
    "Span",
    "ToolCall",
    "TraceStatus",
    "AgentTracer",
    "trace",
    "get_tracer",
    "JSONExporter",
    "JSONLExporter",
    "ConsoleExporter",
]
