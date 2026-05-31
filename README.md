# agent-trace

**Framework-agnostic observability for AI coding agents.**

Every AI agent makes tool calls — search, read files, run commands, call APIs. agent-trace captures every one: what was called, how long it took, whether it succeeded, and what it cost. Zero dependencies. One decorator. Works with any agent framework.

```python
from agent_trace import AgentTracer, ConsoleExporter, JSONExporter

tracer = AgentTracer()
tracer.start_trace("fix-bug-123", model="deepseek-v4-pro")

with tracer.span("research"):
    tc = tracer.tool("web_search", {"query": "nextjs middleware timeout"})
    tc.finish(result_summary="Found 5 results")

with tracer.span("edit"):
    tc = tracer.tool("patch", {"path": "middleware.ts", "old": "timeout=5", "new": "timeout=30"})
    tc.finish(result_summary="Patched")

tracer.set_usage(total_tokens=12450, estimated_cost_usd=0.028)
trace = tracer.finish_trace()
print(tracer.export(trace, ConsoleExporter()))
```

```
╭─ Trace: fix-bug-123  ✓  312ms
├  ID: a1b2c3d4e5f6
├  Model: opencode-go/deepseek-v4-pro
├  Tokens: 12,450  $0.0280
├─ Span: research  ✓  105ms
│   └── tool:web_search  101ms  ✓
│        → Found 5 results
└─ Span: edit  ✓  103ms
    └── tool:patch  101ms  ✓
         → Patched
```

## Why agent-trace?

AI coding agents are becoming critical infrastructure. But most developers have no visibility into what their agents are actually doing — which tools they call, how long operations take, what fails silently, what the cost per-task is.

This gap becomes dangerous when agents run autonomously 24/7. Without observability, you're flying blind.

agent-trace solves this with a **framework-agnostic** approach. It doesn't care if you're using Hermes, Claude Code, Codex CLI, OpenCode, or a custom agent — the tracing primitives work everywhere.

## Features

- **Zero dependencies** — standard library only
- **Framework-agnostic** — works with any Python-based agent
- **Thread-safe** — safe for concurrent agent workloads
- **Structured output** — JSON, JSONL, or human-readable console
- **CLI analyzer** — query trace files for stats, errors, and patterns
- **Decorator API** — `@trace()` for minimal-invasion instrumentation
- **Token/cost tracking** — record usage and estimate cost per trace

## Install

```bash
pip install agent-trace
```

Or from source:

```bash
git clone https://github.com/ko4lax/agent-trace.git
cd agent-trace
pip install -e .
```

## Quick Start

### Manual instrumentation

```python
from agent_trace import AgentTracer, JSONExporter

tracer = AgentTracer()

# Start a trace — typically one per agent task/session
tracer.start_trace("refactor-auth", model="gpt-5.4", provider="openai")

# Wrap work in spans — groups related tool calls
with tracer.span("analyze"):
    tc = tracer.tool("read_file", {"path": "auth.ts"})
    # ... do work ...
    tc.finish(result_summary="Read 156 lines")

# Record token usage
tracer.set_usage(total_tokens=8500, estimated_cost_usd=0.018)

# Finish and export
trace = tracer.finish_trace()
with open("traces.jsonl", "a") as f:
    f.write(tracer.export(trace, JSONLExporter()))
```

### Decorator-based instrumentation

```python
from agent_trace import trace

@trace(track_args=True, sanitize=["api_key"])
def call_llm(prompt: str, api_key: str = "") -> str:
    # Your LLM call here
    return "response..."
```

### CLI analysis

```bash
# Summary statistics
agent-trace stats traces.jsonl

# List all traces
agent-trace list traces.jsonl

# Show a specific trace
agent-trace show traces.jsonl a1b2c3d4e5f6

# Show only failed traces
agent-trace errors traces.jsonl
```

## API Reference

### `AgentTracer`

| Method | Description |
|--------|-------------|
| `start_trace(name, model?, provider?, metadata?)` | Begin a new trace |
| `span(name, metadata?)` | Context manager for a span |
| `tool(name, arguments?, metadata?)` | Create a tool call within current span |
| `set_usage(total_tokens, estimated_cost_usd?)` | Record token/cost for current trace |
| `finish_trace(status?)` | End trace and return it |
| `export(trace, exporter?)` | Export a trace to string |

### `@trace()` decorator

```python
@trace(name="optional-name", track_args=False, sanitize=["secret"])
def your_function(...): ...
```

### Exporters

| Class | Output |
|-------|--------|
| `ConsoleExporter(use_color=True)` | Human-readable tree with colors |
| `JSONExporter(indent=2)` | Pretty-printed JSON |
| `JSONLExporter()` | Single-line JSON (for log files) |

## Use Cases

- **Agent debugging** — find which tool calls fail and why
- **Performance profiling** — identify slow tool calls and spans
- **Cost tracking** — measure per-task token usage and estimated cost
- **CI/CD observability** — trace agent behavior in automated pipelines
- **Multi-agent tracing** — correlate traces across concurrent agent runs

## Real-World Integration

agent-trace is designed to be embedded into existing agent frameworks. Here's how it fits into a typical agent loop:

```python
tracer = AgentTracer()
tracer.start_trace(f"task-{task_id}", model=model_name)

for step in plan:
    with tracer.span(step.name):
        tc = tracer.tool(step.tool_name, step.arguments)
        try:
            result = execute_tool(step)
            tc.finish(result_summary=summarize(result))
        except Exception as e:
            tc.finish(status=TraceStatus.ERROR, error_message=str(e))

tracer.set_usage(total_tokens=token_count, estimated_cost_usd=cost)
trace = tracer.finish_trace()
```

## Contributing

Issues and PRs welcome. Run tests with:

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE).

## Author

[Hanif Nugraha](https://github.com/ko4lax) — building tools for the AI agent ecosystem.
