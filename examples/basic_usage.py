"""
Example: Using agent-trace to instrument an AI agent workflow.
"""

import time
from agent_trace import AgentTracer, ConsoleExporter, JSONExporter, TraceStatus


def main():
    tracer = AgentTracer()
    tracer.start_trace(
        name="fix-bug-123",
        model="deepseek-v4-pro",
        provider="opencode-go",
        metadata={"task": "Fix login timeout", "user": "koala"},
    )

    # Step 1: Research
    with tracer.span("research"):
        tc = tracer.tool("web_search", {"query": "nextjs middleware timeout fix"})
        time.sleep(0.1)
        tc.finish(result_summary="Found 5 relevant results")

    # Step 2: Read file
    with tracer.span("read-source"):
        tc = tracer.tool("read_file", {"path": "middleware.ts"})
        time.sleep(0.05)
        tc.finish(result_summary="Read 42 lines")

    # Step 3: Edit file
    with tracer.span("edit"):
        tc = tracer.tool("patch", {"path": "middleware.ts", "old": "timeout=5", "new": "timeout=30"})
        time.sleep(0.1)
        tc.finish(result_summary="Patched 1 occurrence")

    # Simulate a tool failure
    with tracer.span("test"):
        tc = tracer.tool("terminal", {"command": "npm test"})
        time.sleep(0.2)
        tc.finish(
            status=TraceStatus.ERROR,
            error_message="TypeError: Cannot read properties of undefined",
        )

    # Record token usage
    tracer.set_usage(total_tokens=12450, estimated_cost_usd=0.028)

    trace = tracer.finish_trace()

    # Console output
    print(tracer.export(trace))
    print()

    # JSON output
    print(tracer.export(trace, JSONExporter()))


if __name__ == "__main__":
    main()
