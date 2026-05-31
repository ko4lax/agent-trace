"""Tests for agent_trace core functionality."""

import json
import time

import pytest

from agent_trace import (
    AgentTracer,
    ConsoleExporter,
    JSONExporter,
    JSONLExporter,
    Span,
    ToolCall,
    Trace,
    TraceStatus,
    get_tracer,
    trace,
)


class TestToolCall:
    def test_basic_tool_call(self):
        tc = ToolCall(name="web_search", arguments={"query": "test"})
        assert tc.name == "web_search"
        assert tc.status == TraceStatus.SUCCESS
        assert tc.duration_ms is None

    def test_finish_sets_duration(self):
        tc = ToolCall(name="test")
        tc.finish(result_summary="done")
        assert tc.duration_ms is not None
        assert tc.duration_ms >= 0
        assert tc.result_summary == "done"

    def test_error_tool_call(self):
        tc = ToolCall(name="failing")
        tc.finish(status=TraceStatus.ERROR, error_message="boom")
        assert tc.status == TraceStatus.ERROR
        assert tc.error_message == "boom"

    def test_to_dict(self):
        tc = ToolCall(name="read_file", arguments={"path": "/tmp/x"})
        tc.finish(result_summary="42 lines")
        d = tc.to_dict()
        assert d["name"] == "read_file"
        assert d["arguments"] == {"path": "/tmp/x"}
        assert d["status"] == "success"
        assert d["duration_ms"] is not None
        assert d["result_summary"] == "42 lines"


class TestSpan:
    def test_span_lifecycle(self):
        span = Span(name="research")
        assert span.name == "research"
        assert span.status == TraceStatus.SUCCESS

    def test_add_tool_calls(self):
        span = Span(name="edit")
        tc = ToolCall(name="patch")
        span.add_tool_call(tc)
        assert len(span.tool_calls) == 1

    def test_nested_spans(self):
        parent = Span(name="task")
        child = Span(name="subtask")
        parent.add_child(child)
        assert len(parent.children) == 1

    def test_finish_sets_duration(self):
        span = Span(name="test")
        span.finish()
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_to_dict(self):
        span = Span(name="lint")
        tc = ToolCall(name="terminal")
        tc.finish()
        span.add_tool_call(tc)
        span.finish()
        d = span.to_dict()
        assert d["name"] == "lint"
        assert len(d["tool_calls"]) == 1
        assert d["duration_ms"] is not None


class TestTrace:
    def test_trace_creation(self):
        trace = Trace(name="test-trace", model="gpt-5.4", provider="openai")
        assert trace.name == "test-trace"
        assert trace.model == "gpt-5.4"
        assert len(trace.id) == 12

    def test_add_span(self):
        trace = Trace(name="test")
        span = Span(name="step1")
        trace.add_span(span)
        assert len(trace.spans) == 1

    def test_finish(self):
        trace = Trace(name="test")
        trace.finish()
        assert trace.duration_ms is not None

    def test_to_dict(self):
        trace = Trace(name="test", model="gpt-5.4")
        span = Span(name="step")
        tc = ToolCall(name="search")
        tc.finish()
        span.add_tool_call(tc)
        span.finish()
        trace.add_span(span)
        trace.total_tokens = 1000
        trace.estimated_cost_usd = 0.002
        trace.finish()

        d = trace.to_dict()
        assert d["trace_id"] == trace.id
        assert d["name"] == "test"
        assert d["model"] == "gpt-5.4"
        assert d["total_tokens"] == 1000
        assert d["estimated_cost_usd"] == 0.002
        assert d["summary"]["total_spans"] == 1
        assert d["summary"]["total_tool_calls"] == 1
        assert d["summary"]["total_errors"] == 0


class TestAgentTracer:
    def test_span_stack_initialized_empty(self):
        tracer = AgentTracer()
        assert tracer._span_stack == []

    def test_full_workflow(self):
        tracer = AgentTracer()
        tracer.start_trace("test-workflow")

        with tracer.span("research"):
            tc = tracer.tool("web_search", {"query": "x"})
            tc.finish(result_summary="found")

        with tracer.span("edit"):
            tc = tracer.tool("patch", {"path": "file.py"})
            tc.finish(result_summary="patched")

        trace = tracer.finish_trace()
        assert trace.name == "test-workflow"
        assert len(trace.spans) == 2
        assert trace.status == TraceStatus.SUCCESS

    def test_tool_without_span(self):
        tracer = AgentTracer()
        tracer.start_trace("direct-tool")
        tc = tracer.tool("read_file", {"path": "x.py"})
        tc.finish(result_summary="ok")
        trace = tracer.finish_trace()
        assert len(trace.spans) == 1

    def test_tool_error_propagation(self):
        tracer = AgentTracer()
        tracer.start_trace("error-trace")

        with tracer.span("failing-step"):
            tc = tracer.tool("terminal", {"command": "rm -rf /"})
            tc.finish(status=TraceStatus.ERROR, error_message="Permission denied")

        trace = tracer.finish_trace()
        d = trace.to_dict()
        assert d["summary"]["total_errors"] == 1

    def test_set_usage(self):
        tracer = AgentTracer()
        tracer.start_trace("usage-test")
        tracer.set_usage(total_tokens=5000, estimated_cost_usd=0.01)
        trace = tracer.finish_trace()
        assert trace.total_tokens == 5000
        assert trace.estimated_cost_usd == 0.01

    def test_no_active_trace_raises(self):
        tracer = AgentTracer()
        with pytest.raises(RuntimeError, match="No active trace"):
            tracer.finish_trace()

    def test_completed_traces(self):
        tracer = AgentTracer()
        tracer.start_trace("t1")
        tracer.finish_trace()
        tracer.start_trace("t2")
        tracer.finish_trace()
        assert len(tracer.completed_traces) == 2

    def test_nested_spans_attach_to_parent(self):
        tracer = AgentTracer()
        tracer.start_trace("nested")
        with tracer.span("parent"):
            with tracer.span("child"):
                pass
        trace_obj = tracer.finish_trace()
        assert len(trace_obj.spans) == 1
        assert trace_obj.spans[0].name == "parent"
        assert len(trace_obj.spans[0].children) == 1
        assert trace_obj.spans[0].children[0].name == "child"

    def test_span_marks_error_on_exception(self):
        tracer = AgentTracer()
        tracer.start_trace("failing-span")
        with pytest.raises(ValueError):
            with tracer.span("explode"):
                raise ValueError("boom")
        trace_obj = tracer.finish_trace()
        assert trace_obj.spans[0].status == TraceStatus.ERROR

    def test_export_uses_default_exporter(self):
        tracer = AgentTracer(exporter=JSONExporter())
        trace_obj = Trace(name="exp")
        trace_obj.finish()
        output = tracer.export(trace_obj)
        assert '"name": "exp"' in output


class TestGlobalTracer:
    def test_singleton(self):
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2

    def test_trace_decorator(self):
        tracer = get_tracer()
        tracer.start_trace("decorator-test")

        @trace(name="my-func", track_args=True, sanitize=["secret"])
        def my_func(x, secret="hidden"):
            return x * 2

        result = my_func(21, secret="ssh")
        assert result == 42

        finished = tracer.finish_trace()
        assert finished.name == "decorator-test"
        assert len(finished.spans) >= 1

    def test_trace_decorator_error_path(self):
        tracer = get_tracer()
        tracer.start_trace("decorator-error")

        @trace(name="boom-func")
        def boom():
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError, match="nope"):
            boom()

        finished = tracer.finish_trace()
        tool = finished.spans[0].tool_calls[0]
        assert tool.status == TraceStatus.ERROR
        assert tool.error_message == "nope"


class TestExporters:
    def test_json_exporter(self):
        trace = Trace(name="json-test")
        tc = ToolCall(name="search")
        tc.finish(result_summary="ok")
        span = Span(name="s1")
        span.add_tool_call(tc)
        span.finish()
        trace.add_span(span)
        trace.finish()

        output = JSONExporter().export(trace)
        parsed = json.loads(output)
        assert parsed["name"] == "json-test"
        assert parsed["spans"][0]["name"] == "s1"

    def test_jsonl_exporter(self):
        trace = Trace(name="jsonl-test")
        trace.finish()
        output = JSONLExporter().export(trace)
        assert output.endswith("\n")
        parsed = json.loads(output)
        assert parsed["name"] == "jsonl-test"

    def test_console_exporter(self):
        trace = Trace(name="console-test")
        tc = ToolCall(name="search")
        tc.finish(result_summary="done")
        span = Span(name="step1")
        span.add_tool_call(tc)
        span.finish()
        trace.add_span(span)
        trace.finish()

        output = ConsoleExporter(use_color=False).export(trace)
        assert "Trace: console-test" in output
        assert "tool:search" in output
        assert "done" in output

    def test_console_exporter_model_tokens_and_error(self):
        trace = Trace(name="console-model", model="gpt", provider="openai")
        trace.total_tokens = 1234
        trace.estimated_cost_usd = 0.0042
        tc = ToolCall(name="search")
        tc.finish(status=TraceStatus.ERROR, error_message="failed")
        span = Span(name="step1")
        span.add_tool_call(tc)
        span.finish(status=TraceStatus.ERROR)
        trace.add_span(span)
        trace.finish(status=TraceStatus.ERROR)

        output = ConsoleExporter(use_color=False).export(trace)
        assert "Model: openai/gpt" in output
        assert "Tokens: 1,234  $0.0042" in output
        assert "error: failed" in output

    def test_console_exporter_colors_when_tty(self, monkeypatch):
        trace = Trace(name="tty")
        trace.finish()
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        output = ConsoleExporter(use_color=True).export(trace)
        assert output.startswith("\033")


class TestSummarize:
    def test_summarize_none(self):
        from agent_trace.tracer import _summarize

        assert _summarize(None) is None

    def test_summarize_truncates_long_text(self):
        from agent_trace.tracer import _summarize

        result = _summarize("x" * 250, max_len=10)
        assert result == "xxxxxxxxxx..."
