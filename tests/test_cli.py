"""Tests for CLI commands and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_trace import cli


def _trace_payload(trace_id: str, status: str = "success") -> dict:
    error_count = 1 if status == "error" else 0
    return {
        "trace_id": trace_id,
        "name": f"trace-{trace_id}",
        "status": status,
        "duration_ms": 120,
        "summary": {"total_spans": 1, "total_tool_calls": 1, "total_errors": error_count},
        "spans": [
            {
                "tool_calls": [
                    {
                        "name": "search",
                        "status": status,
                        "error_message": "boom" if status == "error" else None,
                    }
                ]
            }
        ],
    }


def test_load_traces_from_json(tmp_path: Path):
    payload = _trace_payload("abc123")
    p = tmp_path / "trace.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    traces = cli._load_traces(p)
    assert traces == [payload]


def test_load_traces_from_jsonl(tmp_path: Path):
    first = _trace_payload("a1")
    second = _trace_payload("b2", status="error")
    p = tmp_path / "trace.jsonl"
    p.write_text(f"{json.dumps(first)}\n\n {json.dumps(second)}\n", encoding="utf-8")
    traces = cli._load_traces(p)
    assert traces == [first, second]


def test_load_traces_missing_file_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    missing = tmp_path / "missing.json"
    with pytest.raises(SystemExit) as exc:
        cli._load_traces(missing)
    assert exc.value.code == 1
    assert f"File not found: {missing}" in capsys.readouterr().err


def test_cmd_stats_prints_summary(capsys: pytest.CaptureFixture[str]):
    traces = [_trace_payload("a1"), _trace_payload("b2", status="error")]
    cli._cmd_stats(traces)
    out = capsys.readouterr().out
    assert "Traces:       2" in out
    assert "Errors:       1" in out
    assert "Top tools:" in out
    assert "search: 2" in out


def test_cmd_list_prints_rows(capsys: pytest.CaptureFixture[str]):
    cli._cmd_list([_trace_payload("a1")])
    out = capsys.readouterr().out
    assert "a1" in out
    assert "trace-a1" in out
    assert "1 calls" in out


def test_cmd_show_prints_json(capsys: pytest.CaptureFixture[str]):
    trace = _trace_payload("a1")
    cli._cmd_show([trace], "a1")
    out = capsys.readouterr().out
    assert '"trace_id": "a1"' in out


def test_cmd_show_missing_exits(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        cli._cmd_show([_trace_payload("a1")], "nope")
    assert exc.value.code == 1
    assert "Trace not found: nope" in capsys.readouterr().err


def test_cmd_errors_no_errors_message(capsys: pytest.CaptureFixture[str]):
    cli._cmd_errors([_trace_payload("a1")])
    assert "No errors found." in capsys.readouterr().out


def test_cmd_errors_prints_error_details(capsys: pytest.CaptureFixture[str]):
    cli._cmd_errors([_trace_payload("a1", status="error")])
    out = capsys.readouterr().out
    assert "a1  trace-a1" in out
    assert "tool:search  →  boom" in out


def test_main_dispatches_to_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = _trace_payload("a1")
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(json.dumps(payload), encoding="utf-8")

    called: list[list[dict]] = []

    def fake_cmd_stats(traces: list[dict]) -> None:
        called.append(traces)

    monkeypatch.setattr(cli, "_cmd_stats", fake_cmd_stats)
    monkeypatch.setattr("sys.argv", ["agent-trace", "stats", str(trace_file)])
    cli.main()

    assert called == [[payload]]


@pytest.mark.parametrize(
    ("command", "extra_args", "target"),
    [
        ("list", [], "_cmd_list"),
        ("show", ["a1"], "_cmd_show"),
        ("errors", [], "_cmd_errors"),
    ],
)
def test_main_dispatches_other_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    extra_args: list[str],
    target: str,
):
    payload = _trace_payload("a1")
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(json.dumps(payload), encoding="utf-8")

    called: list[tuple] = []

    def fake_cmd(*args):
        called.append(args)

    monkeypatch.setattr(cli, target, fake_cmd)
    monkeypatch.setattr("sys.argv", ["agent-trace", command, str(trace_file), *extra_args])
    cli.main()

    assert called
